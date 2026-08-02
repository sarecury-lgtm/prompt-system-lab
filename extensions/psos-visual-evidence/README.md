# PSOS Browser Evidence Bridge

사용자가 평소 쓰는 Chrome 세션에서 상품 페이지를 열고, 현재 판매 상태와 가격·배송·옵션 정보를 PSOS 실행에 돌려주는 로컬 확장 프로그램이다. 기존 사진 근거 선택 기능도 그대로 포함한다.

## 설치

1. PSOS 서버를 실행한다.

   ```powershell
   python -B C:\Users\jeong\prompt-system-lab\scripts\problem_solving_quality_web.py --open-browser chrome
   ```

2. Chrome에서 `chrome://extensions`를 연다.
3. 오른쪽 위의 `개발자 모드`를 켠다.
4. `압축해제된 확장 프로그램을 로드합니다`를 누른다.
5. 다음 폴더를 선택한다.

   ```text
   C:\Users\jeong\prompt-system-lab\extensions\psos-visual-evidence
   ```

이미 설치한 경우 확장 프로그램 카드의 새로고침 버튼을 누르면 된다.

## 상품 검증

1. PSOS에서 웹 검색을 켜고 요청을 실행한다.
2. 결과가 나온 뒤 Chrome 도구 모음의 PSOS 확장 프로그램을 연다.
3. 자동으로 채워진 실행 ID를 확인하고 `검증 시작`을 누른다.
4. 최초 한 번 Chrome의 웹사이트 접근 권한을 허용한다.
5. 확장 프로그램이 후보 URL을 순서대로 열어 현재 화면을 확인한다.
6. 로그인이나 사람 확인이 필요한 페이지가 열리면 직접 완료한 뒤 확장 프로그램에서 `이어서 검증`을 누른다.

검증이 끝나면 다음 작업이 자동으로 일어난다.

- `connected-browser-verification.json`에 페이지별 영수증 저장
- 부모 실행의 `route.json`과 `result.md`에 Chrome 관찰 결과 반영
- 판매 중단·확인 불가 상품을 최종 후보에서 제외하도록 수정 실행 시작
- 유효 후보 수가 부족하면 웹 검색으로 다른 판매처 보충

확장 프로그램은 비밀번호나 Chrome 쿠키를 PSOS에 전달하지 않는다. 페이지에서 실제로 렌더링된 상품명, 가격 문구, 배송 문구, 중량, 선택 옵션, 구매 버튼, 판매 중단 신호와 본문 해시만 로컬 PSOS 서버에 보낸다.

## 사진 근거

확장 프로그램 메뉴의 `현재 탭에서 사진 근거 고르기`를 누르면 기존 사진 선택 화면이 열린다. 실행 ID와 후보명을 입력하고 필요한 이미지만 선택해 현재 Evidence Bundle에 추가할 수 있다.
