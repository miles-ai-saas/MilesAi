import { useEffect, useMemo, useState } from "react";
import { defaultTraceTurnIndex, listTraceTurns } from "@/features/agents/lib/agent-trace";
import type { ChatMessage } from "@/features/agents/lib/chat-sessions";

export function useTraceTurnSelection(messages: ChatMessage[], sessionKey?: string) {
  const turns = useMemo(() => listTraceTurns(messages), [messages]);
  const [selectedTurnIndex, setSelectedTurnIndex] = useState(0);

  useEffect(() => {
    setSelectedTurnIndex(defaultTraceTurnIndex(turns));
  }, [turns.length, sessionKey]);

  return { turns, selectedTurnIndex, setSelectedTurnIndex };
}
