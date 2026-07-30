# PSOS ChatGPT Bridge extension

Optional Chrome extension for `scripts/problem_solving_manual_web.py`.

## Install

1. Start the local bridge:

   ```powershell
   python -B scripts/problem_solving_manual_web.py
   ```

2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked** and select this directory.
5. Open `https://chatgpt.com/` and pin the extension.

## Use

1. Start a request in the local bridge page.
2. On the intended ChatGPT tab, choose **현재 PSOS 작업 가져오기**.
3. Review the inserted prompt and press ChatGPT's send button yourself.
4. Wait until the response has completely finished.
5. Choose **이 작업의 새 답변 반환**.
6. If another PSOS stage remains, review the newly inserted prompt and send it yourself.

The extension stays bound to one run until that run completes. It records the assistant-response state when each prompt is inserted and refuses to return an older response or a response that is still streaming.

It also refuses to overwrite a non-empty ChatGPT composer. Clear or save any draft before importing a PSOS prompt.

The extension intentionally does not click ChatGPT's send button. This keeps each transfer visible and avoids treating brittle DOM automation as an execution guarantee. ChatGPT DOM changes can still require selector maintenance.
