# MABC-FINAL

AI 요약 초안 vs 원본 대조 검수 웹 서비스 — MABC2026 결선 MVP.

## 개요
- 원본 자료(xlsx, 텍스트 표, 텍스트, md, 기억 파일 json)와 AI 요약 초안을 받아 수치·주장을 대조
- cited figure check 스킬을 호출해 5라벨 판정(일치/불일치/값은 있으나 항목 대응이 다름/원본에 없음/확인 불가)
- 수치 계산은 코드가 직접 수행, 모델 호출은 Solar Pro 4만 사용
- 버전 업 시 이전 검수 결과를 이용해 변경분을 재검증

## 제약
- Solar Pro 4 API만 호출
- 타 LLM API, 유료 외부 API, DB, 로그인·인증 사용 금지
- API 키는 서버 사이드에만, 클라이언트 코드/저장소에는 넣지 않음
- 모델 호출 실패 시 다른 모델로 넘어가지 않고 재시도, 부분 결과 표시

## 입력
- xlsx, 텍스트 표, 텍스트, md, 기억 파일 json
- 이미지/URL/PDF는 받지 않음

## 산출물
- 검수 표(판정, 잘못된 부분, 근거, 수정 제안, 확인 여부)
- before/after 시각화(수정 부분 빨강/파랑)
- 출력 파일 2개(고쳐진 파일, 기억 파일) 다운로드
- 기억 파일 재업로드 시 재검증 대상 감소 표시
- 예시 버튼으로 전체 흐름 시연 가능

## 개발
- 작업 폴더: C:\project\MABC-FINAL
- GitHub: https://github.com/Loda1002/MABC-FINAL
- Hermès 안에서 개발, 예선에서 사용한 스킬 활용

## 검증 게이트
typecheck -> lint -> unit test -> integration -> e2e
- unit: 스킬 출력을 고정 샘플로 저장, Solar Pro 4 없이 실행
- integration: 스킬 실제 호출, 출력 형식만 확인
- e2e: 예시 버튼 -> 검수 표 -> 파일 다운로드 -> 기억 파일 재업 -> 재검증 건수 감소 확인
