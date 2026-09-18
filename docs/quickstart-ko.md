# Trolley 빠른 시작

## 서버 운영자: CLI로 사용자 추가

```bash
docker compose exec trolley trolley operator add-user
```

이메일 → 역할 → 그룹 → 새 그룹의 Target → 최종 확인 순서로 진행합니다.
기본 관리자·그룹은 자동 생성하지 않습니다. 기존 그룹의 Target은 마법사에서
변경하지 않습니다. 설정 저장 후 초대 메일을 보낼 수 있습니다.

- user: 그룹 Target의 Operation 실행
- developer: 실행 + 스키마 확인·읽기 전용 SQL 탐색
- admin: 실행 + 탐색 + Operation 생성·관리

모든 역할은 **사용자 → 그룹 → Target** 경계를 따릅니다. Operation을 만들면
그 Target에 접근 가능한 모든 그룹 멤버에게 공개됩니다. 개별 Operation 권한은
없습니다. 다른 경계가 필요하면 Target과 DB 권한을 분리하세요.

## 사용자: 연결하고 질문하기

1. 이메일의 onboarding.md URL을 AI에게 전달해 연결을 요청합니다.
2. API 키는 대화가 아닌 클라이언트 인증 설정에 직접 입력합니다.
3. MCP 재연결 후 “Trolley에서 내가 할 수 있는 일을 알려줘”라고 요청합니다.

MCP가 없는 클라이언트라면 공식 문서에 따라 확장·브리지를 설치하거나
지원 클라이언트를 사용합니다. 사용자 PC에 Trolley 서버를 설치할 필요는 없습니다.

## 관리자: 데이터 도구 만들기

스키마·데이터 설명을 확인하고 SQL을 검증한 다음 Operation을 만듭니다.
일회성 조회에는 query_target을 쓰면 되므로 Operation을 만들 필요가 없습니다.

caller는 인증된 계정의 소유 데이터로 제한하고, shared는 자동 소유자 필터 없이
승인된 결과를 제공합니다. 그룹 권한과 결과의 소유자 제한은 서로 다른 개념입니다.
직접 SQL에는 caller 필터가 적용되지 않습니다.

[운영자 명령](operator-wizard.md) · [상세 가이드](guide.md) · [배포](deployment.md)
