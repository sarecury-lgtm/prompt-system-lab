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
2. On a ChatGPT tab, open the extension and choose **대기 중 작업 가져오기**.
3. Review the inserted prompt and press ChatGPT's send button yourself.
4. When the response is complete, choose **마지막 답변 반환**.
5. If another PSOS stage is required, the extension inserts the next prompt automatically.

The extension intentionally does not click ChatGPT's send button. This keeps each transfer visible and avoids treating brittle DOM automation as an execution guarantee.
