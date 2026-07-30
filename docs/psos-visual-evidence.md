# PSOS Visual Evidence

PSOS Quality Core의 Evidence Bundle을 브라우저에서 검토하고, 사용자가 직접 고른 웹 이미지를 후보별 근거로 추가하는 범용 시각 근거 계층이다.

## 흐름

```text
PSOS 결과
→ 근거 갤러리
→ 유지 / 의심 / 제외 판정
→ 현재 웹페이지에서 사진 선택
→ 후보명·출처 유형과 함께 전송
→ 이미지 로컬 보존
→ 갤러리에서 원본과 보존본 검토
→ 판정을 반영한 child revision
```

## 안전 경계

- 현재 탭의 사용자가 체크한 사진만 최대 24장 전송
- 후보명과 판매자 제공·구매자 후기·기사·미확인 출처를 사용자가 직접 지정
- `data:`·`blob:`·인증 정보 URL과 stale bundle hash 거부
- 사설·로컬·예약 IP 차단과 리다이렉트 재검사
- JPEG·PNG·GIF·WebP·AVIF만 허용
- 장당 12MB, 가져오기당 64MB 제한
- MIME과 실제 매직바이트 일치 검사
- `evidence/images/<sha256>.<확장자>`에 원자적으로 저장
- 실패 시 원본 URL과 실패 이유 보존

## 실행

```powershell
python -B .\scripts\problem_solving_quality_web.py --open-browser chrome
```

확장 폴더:

```text
extensions/psos-visual-evidence
```

## 검증

Playwright가 실제 Chromium에 압축 해제 확장을 로드해 사진 선택, 후보 연결, 서버 전송, 로컬 보존, production 갤러리 렌더링을 자동 검증한다.

실제 쇼핑몰별 로그인·무한 스크롤·lazy loading·anti-hotlink 정책은 사용자 Chrome에서 별도 확인이 필요하다.
