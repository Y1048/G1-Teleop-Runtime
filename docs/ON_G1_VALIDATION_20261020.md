# 기존 G1에서의 무모터 격리 실행 결과

2026-10-20, aarch64 / L4T R35.3.1. 원본 설치를 수정하지 않고 별도 복사본을 사용했다.

## 실제 수행

- 실행 패키지 회수: SHA256 `53d82a68036925142b820a513c0cebb9454420a90cd18f8ef6d18927601a7cac` 일치.
- bubblewrap의 PID·네트워크·장치·홈 격리 사용. C++ actuator는 복사본에서 제외.
- Ubuntu 20.04 bubblewrap의 미지원 `--clearenv`를 제거하고 subprocess에 정제된 환경을 직접 전달하도록 검증 도구만 수정.
- 장치 없는 원본 구성: Valleg 탐지 실패로 5.31초에 종료, 종료 코드 1. 실패 정리 경로 완료.
- **Valleg 대기 모형 사용**: 실제 server/IK/heading 실행, IK ready 및 서버 ACK 확인. 30초에 Enter를 보내 31.53초에 종료 코드 0. 감독 프로세스의 강제 종료 없음.
- 원본 startup의 내부 SIGTERM/SIGKILL fallback 코드는 유지됐으며, 모든 개별 자식이 자발적으로 종료했다고까지 주장하지 않는다.
- 종료 후 관련 actuator/heading/IK/server 잔류 프로세스 없음.
- 기존 설치와 payload의 manifest 10,318개 기록 모두 재검사, 불일치 없음.

## 범위 밖

실제 Valleg/HID, Quest, 카메라, LowState, 실물 UDP 네트워크, TensorRT 추론, 모터 응답은 검사하지 않았다.
장치와 eth0가 없는 namespace에서 카메라 대기·DDS 초기화 실패는 예상된 결과다.
heading의 zero command도 격리 loopback 안에서만 발생했으며 실제 로봇 actuator는 실행하지 않았다.

**결론: 격리 소프트웨어 시작·통신·Enter 종료 경로 확인. 실제 장치 포함 전체 통합 PASS는 아님.**

Release의 `validation_evidence.tar.gz`에 console/result/component 로그 및 원본 보존 대조 결과가 있다.
해당 아카이브의 IK 기록은 격리 실행 기록이며 실제 G1 센서 측정 데이터가 아니다.
