# Documentation Changelog

리눅스 엔지니어 실무 시나리오 학습 플랫폼 설계 및 진행 과정의 버전 기록입니다.

## [v0.4.0] - 2026-11-27
### Added
- **레벨별 표준 학습 커리큘럼(`curriculum/curriculum.json`) 구현**:
  - Junior / Mid-level / Senior / C-Level 4대 커리어 트랙, 교육 목표, 선수 과목(Prerequisites), 트랙 승급 기준 및 배지 시스템 도입
  - 완료 시나리오 가중치 기반 **6대 실무 역량 프로파일** 실시간 산출 API(`GET /api/curriculum`) 추가
- **단계별 실무 시나리오 12종 확장 구현(`scenarios/*.json`)**:
  - Junior 3종(`j01`~`j03`), Mid-level 3종(`m01`~`m03`), Senior 3종(`s01`~`s03`), C-Level 3종(`c01`~`c03`)
- **선언적 규칙 기반 엔진(Declarative Rule Engine) 리팩토링**:
  - `provisioner.py` 및 `evaluator.py`의 시나리오 ID 하드코딩을 제거하고 `command_rules` / `state_checks` 기반 범용 엔진으로 업그레이드
- **커리큘럼 로드맵 UI 및 전체 트랙 E2E 검증(5/5 PASS)**:
  - 문서 파일: [v0.4.0_curriculum_and_scenarios.md](./v0.4.0_curriculum_and_scenarios.md)

## [v0.3.0] - 2026-11-24
### Added
- **MVP 시스템 구현 완료**:
  - `scenarios/`: 주니어~C레벨 4종 Scenario-as-Code 정의 파일
  - `backend/`: Lab Provisioner 추상화, 다차원 자동 채점 엔진, B2C 구독 티어 API 및 SQLite 영속화
  - `frontend/`: 가상 Slack/Jira, 실시간 메트릭, 웹 터미널, C레벨 의사결정 보드 통합 UI
  - `infra/onprem/`: Firecracker MicroVM 런처, VLAN 30 Egress 차단(`nftables`), Docker Compose
  - `tests/`: End-to-End 자동화 테스트 스위트 (4/4 PASS)
- **구현 보고서 작성**: [v0.3.0_implementation_report.md](./v0.3.0_implementation_report.md)

## [v0.2.0] - 2026-11-22
### Added
- **B2C(개인 구독) 중심 서비스 기획**: 구독 티어(Free/Pro/Executive), 게이미피케이션, 개인 역량 포트폴리오 기능 정의
- **온프레미스(On-Premises) 인프라 아키텍처**: 물리 서버 구성(Control/Compute/Storage), KVM+Firecracker 기반 MicroVM 고밀도 운영, VLAN 기반 네트워크 격리 및 로컬 미러 서버 설계
- **하드웨어 사이징 가이드**: 초기 MVP(동접 50명) 및 성장기(동접 300명) 기준 서버 스펙 제안
- 문서 파일: [v0.2.0_b2c_onprem_architecture.md](./v0.2.0_b2c_onprem_architecture.md)

## [v0.1.0] - 2026-11-22
### Added
- **초기 종합계획서 수립**: 주니어/중니어/시니어/C레벨 커리큘럼, 전체 시스템 아키텍처, 핵심 기능, 기술 스택, 단계별 로드맵 작성
- 문서 파일: [v0.1.0_master_plan.md](./v0.1.0_master_plan.md)
