# PSOS Quality Layer

메인 PSOS 실행 결과에 요청별 완료 조건, 결과 검증, 제한된 보충 실행, 사용자 근거 검토와 명시적 시각 근거 수집을 추가하는 실험적 품질 계층이다.

수동 ChatGPT 브리지의 기능이 아니다. 기존 Codex 기반 PSOS와 로컬 작업실을 재사용한다.

## 실행

```powershell
cd "C:\Users\jeong\prompt-system-lab"
git switch agent/psos-quality-core
git pull
python -B .\scripts\problem_solving_quality_web.py --open-browser chrome
```

기본 주소는 `http://127.0.0.1:8765`다. 기존 PSOS 서버가 켜져 있다면 먼저 `Ctrl+C`로 종료한다.

CLI만 사용할 때는 다음 진입점을 쓴다.

```powershell
python -B .\scripts\problem_solving_os_quality_runtime.py --request "해결할 요청"
```

## 결과 흐름

```text
요청
→ Goal Ledger와 route
→ Result Contract 생성
→ 실제 실행
→ 계약 검증
→ 안전한 경로만 최대 1회 보충
→ Evidence Bundle 생성
→ PROMPT 경로이면 생성 단계 진단
→ 필요하면 웹페이지에서 시각 근거 선택·로컬 보존
→ 사용자 검토
→ 필요할 때 원본을 보존한 새 수정 실행
```

## PROMPT 생성 경로 진단

PROMPT가 포함된 실행은 최종 프롬프트를 바로 고치는 대신 다음 생성 단계를 비교한다.

```text
사용자 원문
→ Goal Ledger
→ Prompt Compiler baseline
→ PROMPT 실행기 입력
→ 최종 프롬프트
```

run 디렉터리에 다음 파일이 생성된다.

```text
prompt_generation_trace.json
prompt_generation_trace.md
```

기록에는 단계별 크기, 구간별 팽창, 최종 프롬프트의 유사 규칙 쌍, 평면 Ledger·additive baseline·중복 입력·형식 압력 신호가 포함된다. 이 진단은 기존 결과를 수정하지 않고 원인을 찾기 위한 자료만 남긴다.

기존 run을 따로 진단할 때는 다음을 사용한다.

```powershell
cd "C:\Users\jeong\prompt-system-lab"
python -B .\scripts\problem_solving_prompt_trace.py --run-dir .\runs\RUN_ID
```

구조적 원인과 비교 실험 기준은 `docs/prompt-generation-causal-audit.md`에 정리돼 있다.

## 웹 근거 검토

Evidence Bundle이 있는 실행을 열면 결과 아래에 `근거 직접 검토`가 표시된다.

각 사진·링크·파일·receipt에 다음 판정을 남길 수 있다.

- `유지`: 최종 결과에서 계속 사용한다.
- `의심`: 다시 확인하고, 확인할 수 없으면 단정을 낮춘다.
- `제외`: 최종 결론의 근거로 사용하지 않는다.

판정은 `evidence_review.json`에 저장되며 현재 `evidence_bundle.json`의 SHA-256과 묶인다. 오래된 화면이나 다른 실행의 판정을 섞으면 저장이 거부된다.

`판정 반영해 결과 수정`은 원래 `result.md`를 덮어쓰지 않는다. 부모 실행에 다음 기록을 남기고 별도의 자식 PSOS 실행을 만든다.

```text
evidence_revision_context.md
evidence_revision_request.json
```

자식 실행은 `유지` 근거를 보존하고, `의심` 근거를 다시 확인하거나 표현을 약화하며, `제외` 근거와 그 근거에만 의존한 주장을 제거한다. 대체 URL·가격·후기·사진을 만들어서는 안 된다.

## 웹페이지 사진을 후보에 연결

Chrome 확장 프로그램은 현재 페이지에서 조건에 맞는 이미지 후보를 보여 주고, 사용자가 체크한 사진만 PSOS에 전송한다.

확장 폴더:

```text
extensions/psos-visual-evidence
```

설치:

1. Chrome에서 `chrome://extensions`를 연다.
2. `개발자 모드`를 켠다.
3. `압축해제된 확장 프로그램을 로드합니다`를 누른다.
4. 위 폴더를 선택한다.

사용:

1. PSOS 결과의 `psos-...` 실행 ID를 확인한다.
2. 사진이 있는 상품·후기·숙소·의류·중고품 등의 페이지를 연다.
3. 확장 아이콘을 누른다.
4. 실행 ID, 후보명, 사진 출처 유형을 입력한다.
5. 필요한 사진만 골라 추가한다.
6. PSOS 결과 화면을 새로고침한다.

후보명은 AI가 추측하지 않고 사용자가 직접 지정한다. 사진 출처는 다음 중 하나로 저장한다.

- 판매자 제공
- 구매자 후기
- 기사·편집 자료
- 미확인

가져온 bundle은 `version: 2`, `subject_mapping: explicit`로 확장된다. 기존 결과 전체 근거는 `result` subject에 남고, 새 사진은 사용자가 정한 candidate subject에 연결된다. 기존 판정은 evidence ID 기준으로 보존되고 새 사진만 `미검토`로 추가된다.

추가 기록:

```text
visual_evidence_imports.json
evidence/images/<sha256>.<확장자>
```

기록에는 이전·새 bundle SHA-256, 후보 ID, 원본 페이지, 수집 시각, 추가된 evidence ID, 중복 URL, 로컬 보존 성공·실패와 총 바이트 수가 남는다.

## 사진 원본 로컬 보존

선택한 외부 이미지는 가능한 경우 run 폴더에 콘텐츠 주소 방식으로 저장한다.

- JPEG·PNG·GIF·WebP·AVIF만 허용
- 응답 MIME과 실제 매직바이트가 일치해야 함
- 장당 최대 12MB, 한 번 가져오기 전체 최대 64MB
- 최대 4회 리다이렉트와 각 도착 URL을 다시 검사
- 사설·로컬·예약 주소와 인증 정보 포함 URL 차단
- 파일명은 이미지 내용의 SHA-256으로 결정
- 원본 URL·최종 URL·실제 MIME·바이트 수·SHA-256을 Evidence Bundle에 보존

다운로드 실패는 전체 가져오기를 거짓 성공이나 전면 실패로 바꾸지 않는다. 해당 항목은 원격 URL을 유지하고 `archive.status: unavailable`과 실패 이유를 남긴다. 따라서 핫링크 차단이나 로그인 쿠키가 필요한 이미지도 원본 페이지에서 다시 확인할 수 있다.

## 권한과 안전 경계

확장 프로그램은 다음 권한만 사용한다.

- 사용자가 아이콘을 누른 현재 탭에 대한 일시 접근
- 로컬 `127.0.0.1:8765` 또는 `localhost:8765` PSOS 서버 접근
- 마지막 실행 ID·후보명·출처 유형의 로컬 저장

자동으로 모든 이미지를 전송하지 않는다. 한 번에 사용자가 고른 최대 24장만 전송한다. `data:`·`blob:` URL, 인증 정보가 포함된 URL, 오래된 bundle SHA는 서버에서 거부한다.

## 현재 경계

- PROMPT 진단은 구조와 반복을 추적하며, 프롬프트의 도메인 정확성 자체를 판정하지 않는다.
- 쿠키·로그인이 필요한 이미지나 서버가 직접 요청을 막는 이미지는 로컬 보존에 실패할 수 있다. 이때 원본 URL과 실패 이유만 남는다.
- 후보 연결은 사용자가 직접 지정한다. 페이지 문맥을 보고 후보명을 자동 추측하지 않는다.
- 완료 조건과 사진의 주장별 자동 연결은 아직 하지 않는다. 사진은 후보 단위로 연결된다.
- CODE·PROJECT는 중복 파일 변경 위험 때문에 계약 미충족 시 자동 보충 실행을 하지 않는다.
- 품질 계층은 아직 Draft PR의 별도 진입점이며 canonical `problem_solving_os.py`를 대체하지 않는다.
- 서버·보안 경계·브라우저 스크립트는 자동 테스트했지만, 실제 사용자 Chrome에서 여러 쇼핑몰 페이지를 대상으로 한 수동 실사용 검증은 남아 있다.
