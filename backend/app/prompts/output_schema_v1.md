# Output Schema v1

只输出合法 json 对象，不要 Markdown 围栏或额外文字：

{
  "reply": "最终在纸面显示的回应",
  "mode": "companion | mirror | judgment | root_cause | decision | execution | grounding | challenge | quiet | safety",
  "safety_level": "normal | elevated | critical",
  "should_ask": false,
  "memory_candidates": []
}

reply 必须非空。memory_candidates 最多 3 条，只能是等待后续规则或用户确认的候选，不能声称已经写入长期记忆。
