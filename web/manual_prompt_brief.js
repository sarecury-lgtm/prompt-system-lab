(() => {
  const originalStagePresentation = stagePresentation;

  stagePresentation = function promptBriefStagePresentation(session) {
    const phase = String(session?.phase || "");

    if (phase.endsWith("_prompt_brief")) {
      return {
        step: "프롬프트 1/2",
        title: "요구를 하나의 작업 구조로 압축하기",
        detail: "원문·Goal Ledger·기존 baseline을 Prompt Build Brief 하나로 통합합니다.",
        badge: "일반 ChatGPT · 새 채팅",
        badgeKind: "normal",
        action: "현재 지시문을 복사한 뒤 반드시 새 ChatGPT 채팅을 열어 보내세요. 받은 JSON 전체를 아래 칸에 붙이면 최종 프롬프트 단계로 넘어갑니다.",
        note: "기존 라우터 채팅을 이어 쓰면 이전 원문 문맥이 남아 단일 Brief 구조를 검증할 수 없습니다. 새 채팅이 필수입니다.",
        responseLabel: "Prompt Build Brief JSON 전체 붙여넣기",
        responseHelp: "ChatGPT가 반환한 JSON 객체 전체를 수정하지 말고 그대로 붙이세요.",
        responsePlaceholder: "Prompt Build Brief JSON 전체를 여기에 붙여넣으세요.",
        submitLabel: "Brief 검사하고 최종 단계로",
        copyLabel: "1. Brief 지시문 복사",
      };
    }

    if (phase.endsWith("_prompt_final")) {
      return {
        step: "프롬프트 2/2",
        title: "Brief만 보고 최종 프롬프트 만들기",
        detail: "이 단계에는 압축된 Brief만 전달되며 원문·전체 Ledger·baseline은 다시 넣지 않습니다.",
        badge: "일반 ChatGPT · 다시 새 채팅",
        badgeKind: "normal",
        action: "현재 지시문을 복사한 뒤 앞 단계와도 분리된 새 ChatGPT 채팅을 열어 보내세요. 받은 JSON 전체를 아래 칸에 붙이면 최종 프롬프트만 저장됩니다.",
        note: "Brief를 만든 채팅을 이어 쓰면 모델이 원래 입력을 기억해 구조 개입의 효과를 흐릴 수 있습니다. 반드시 다시 새 채팅을 사용하세요.",
        responseLabel: "최종 PROMPT 실행 결과 JSON 붙여넣기",
        responseHelp: "execution.result_markdown에 완성된 프롬프트가 들어 있는 JSON 전체를 붙이세요.",
        responsePlaceholder: "최종 PROMPT 실행 결과 JSON 전체를 여기에 붙여넣으세요.",
        submitLabel: "최종 프롬프트 확인",
        copyLabel: "1. 최종 생성 지시문 복사",
      };
    }

    return originalStagePresentation(session);
  };

  if (typeof currentSession !== "undefined" && currentSession && currentSession.state !== "completed") {
    applyPresentation(currentSession);
  }
})();
