"""意图解析 & 路由模块（SDD 模块 1）。

两级路由策略：
1. LLM 路由（可选）：本地模型理解指令 → 结构化执行计划；
2. 关键词规则路由（兜底）：触发词命中 → 按首个命中位置排序成串行计划。

边界判断：主观创意类指令（叙事 / 情绪剪辑 / 创意转场）不做全自动执行，
返回提示而不生成执行计划。
"""
from __future__ import annotations

import json
import re

from . import llm
from .models import ExecutionPlan, PlanStep
from .registry import REGISTRY, SkillRegistry

# 主观创意类指令特征词（SDD 第 6 节约束 1）
SUBJECTIVE_PATTERNS = ["叙事", "情绪剪辑", "创意转场", "讲故事", "氛围感剪辑", "艺术感"]


class IntentRouter:
    def __init__(self, registry: SkillRegistry = REGISTRY, use_llm: bool = True) -> None:
        self.registry = registry
        self.use_llm = use_llm

    def route(self, instruction: str, media_summary: str = None) -> ExecutionPlan:
        if self.use_llm and llm.is_available():
            try:
                return self._route_by_llm(instruction, media_summary)
            except Exception:
                pass  # 模型路由失败自动降级到规则路由
        return self._route_by_rules(instruction)

    # ---------------------------------------------------------------- 规则路由

    def _route_by_rules(self, instruction: str) -> ExecutionPlan:
        matched = self._match_skills(instruction)
        if not matched:
            if self._is_subjective(instruction):
                return ExecutionPlan(
                    intent="rejected",
                    explanation=(
                        "主观创意类需求（镜头叙事 / 情绪剪辑 / 创意转场）不做全自动执行，"
                        "仅提供辅助建议。当前版本支持的标准化任务见 `clip-agent skills`。"
                    ),
                )
            names = "、".join(
                f"{s.meta.skill_id} {s.meta.name}" for s in self.registry.enabled()
            )
            return ExecutionPlan(
                intent="unclear",
                steps=[],
                explanation=(
                    "未能理解该指令或未匹配到可用 Skill。"
                    f"当前可用 Skill：{names}。请换一种说法，或明确任务范围。"
                ),
            )

        steps = [
            PlanStep(skill_id=s.meta.skill_id, params=_extract_params(instruction))
            for s in matched
        ]
        return ExecutionPlan(
            intent="、".join(s.meta.name for s in matched),
            steps=steps,
            explanation="规则路由命中 "
            + " → ".join(s.meta.name for s in matched),
            source="rule",
        )

    def _match_skills(self, instruction: str) -> list:
        """触发词命中：按首个命中位置排序（越早出现越先执行）。"""
        hits = []
        for skill in self.registry.enabled():
            positions = [
                instruction.find(t) for t in skill.meta.triggers if t in instruction
            ]
            if positions:
                hits.append((min(positions), skill))
        hits.sort(key=lambda x: x[0])
        return [s for _, s in hits]

    @staticmethod
    def _is_subjective(instruction: str) -> bool:
        return any(p in instruction for p in SUBJECTIVE_PATTERNS)

    # ---------------------------------------------------------------- LLM 路由

    def _route_by_llm(self, instruction: str, media_summary: str = None) -> ExecutionPlan:
        manifest = json.dumps(
            [
                {
                    "skill_id": s.meta.skill_id,
                    "name": s.meta.name,
                    "desc": s.meta.desc,
                    "params": s.meta.params,
                    "input": s.meta.input,
                }
                for s in self.registry.enabled()
            ],
            ensure_ascii=False,
        )
        system = (
            "你是剪辑辅助 Agent 的意图路由器，负责把用户的自然语言指令翻译成执行计划。\n"
            f"可用 Skill 清单：{manifest}\n"
            "只输出一个 JSON 对象，不要输出其他文字，格式：\n"
            '{"intent":"意图概述","steps":[{"skill_id":"S001","params":{...}}],'
            '"explanation":"一两句给用户看的解释"}\n'
            "约束：\n"
            "1. steps 按执行顺序排列，skill_id 必须来自清单；\n"
            "2. params 的键必须来自对应 Skill 的 params 定义，能从指令中提取才填；\n"
            "3. 主观创意类需求（镜头叙事、情绪剪辑、创意转场等）输出 "
            '{"intent":"rejected","steps":[],"explanation":"原因"}；\n'
            '4. 无法匹配时输出 {"intent":"unclear","steps":[],"explanation":"需要澄清的问题"}。'
        )
        user = f"用户指令：{instruction}"
        if media_summary:
            user += f"\n当前素材：{media_summary}"
        text = llm.chat(system, user)
        return self._parse_llm_plan(text)

    def _parse_llm_plan(self, text: str) -> ExecutionPlan:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型输出中未找到 JSON")
        data = json.loads(text[start : end + 1])
        known = {s.meta.skill_id: s for s in self.registry.enabled()}
        steps = []
        for step in data.get("steps", []):
            skill = known.get(step.get("skill_id"))
            if skill is None:
                continue
            params = {
                k: v
                for k, v in (step.get("params") or {}).items()
                if k in skill.meta.params
            }
            steps.append(PlanStep(skill_id=skill.meta.skill_id, params=params))
        return ExecutionPlan(
            intent=data.get("intent", ""),
            steps=steps,
            explanation=data.get("explanation", ""),
            source="llm",
        )


def _extract_params(instruction: str) -> dict:
    """规则路由的轻量参数提取：dB 阈值、前 N 个高光、静音时长下限。"""
    params = {}
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*dB", instruction)
    if m:
        params["silence_threshold"] = float(m.group(1))
    m = re.search(r"前\s*(\d+)\s*[个条段]", instruction)
    if m:
        params["top_n"] = int(m.group(1))
    m = re.search(r"(?:静音|无声)[^0-9]{0,6}(\d+(?:\.\d+)?)\s*秒", instruction)
    if m:
        params["min_duration"] = float(m.group(1))
    return params
