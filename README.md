# G1 Teleop Runtime

G1 실행 패키지 전달을 위한 별도 저장소입니다. 기존 개발 저장소와 이력을 공유하지 않습니다.
핵심 C++ 소스와 Unity 프로젝트는 포함하지 않습니다. Python은 유지합니다.

## 현재 상태

**준비 단계입니다. clone만으로 로봇을 실행할 수 없습니다.**
G1에 보관된 실행 패키지는 아직 이 저장소의 Release에 업로드하지 않았습니다.
로봇이 꺼져 있어 회수하지 않았으며, 실제 전체 시작·종료도 아직 검증 전입니다.

- 기존·새 G1: Ubuntu 20.04.6, JetPack 5.1.1 / L4T R35.3.1, 커널 5.10.104-tegra
- aarch64, CUDA 11.4, TensorRT 8.5.2, Python 3.8.10, PyTorch 2.0.0+nv23.05, eth0
- Quest APK + G1 내부 서버·IK·입력·C++ 제어기 구성
- 해당 기준의 하체 입력은 Valleg입니다.

## 포함된 준비물

- `validation/prepare.py`: 원본 패키지를 검증하고 별도 복사본을 준비합니다.
- `validation/run_isolated.py`: Linux namespace 안에서 모터 실행파일 없이 시작·종료를 시도합니다.
- [실행 절차와 한계](docs/START_HERE.txt)
- [실제 수행한 검사](docs/VALIDATION.txt): PC 오프라인 검사 5개 통과. 실기 검증 아님.
- [전달 파일 목록](artifacts.json): 업로드 전 파일의 이름·해시와 현재 가용 상태
- [라이선스 상태](docs/LICENSING.md)

원본 `start_all.sh`를 staging에서 그대로 실행하지 마세요. 절대경로가 기존 설치를 가리킬 수 있습니다.
검증 도구는 bubblewrap이 없거나 격리가 불가능하면 중단하며 자동 설치·비격리 실행을 하지 않습니다.
실제 카메라·Quest·입력 장치·LowState 연결 검사는 별도입니다.

## 다음 단계

G1 전원 연결 후 실행 패키지 회수 → 별도 경로 무모터 시작·종료 검증 → 필요한 외부 고지/소스 자료 동봉 → Release 자산 업로드.
APK·바이너리는 원문 소스를 포함하지 않지만 역공학 불가능을 보장하지는 않습니다.
