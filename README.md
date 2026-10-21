# G1 Teleop Runtime

기존 개발 저장소와 분리된 G1 실행 패키지입니다. **핵심 C++ 소스·Unity 프로젝트는 포함하지 않습니다.** Python과 빌드된 제어기, 실행 자료를 전달하며 Quest APK는 아래 Release에서 받습니다.

아래 명령은 **새 G1에 로그인한 `unitree` 계정의 터미널**에서 실행합니다. 설치기는 모터를 실행하지 않으며, 실제 모터 실행은 마지막 단계에서 직접 선택합니다.

현재 전달본: **v0.1.1-pre.20261021 — 핵심 C++ 실행파일의 정적 심볼 제거본**. G1 격리 로더 비교와 모터 제외 시작·종료 검사를 통과했습니다. 실제 모터 재검증은 하지 않았습니다. [검증 상세](docs/STRIPPED_BINARY_20261021.md)

## 1. 환경과 의존성 준비

| 구분 | 필요한 것 / 처리 방식 |
|---|---|
| G1 기준 환경 | aarch64, Ubuntu **20.04.6**, JetPack **5.1.1 / L4T R35.3.1**, 커널 **5.10.104-tegra**, `eth0` |
| NVIDIA / Python 기준 | CUDA **11.4**, TensorRT **8.5.2**, 시스템 Python **3.8.10**, PyTorch **2.0.0+nv23.05**. 다른 버전으로 자동 교체하지 않음 |
| 기본 도구 | `git`, `python3`, `sudo`, `bash`, `pgrep`(procps), `sha256sum`(coreutils), APT/dpkg. `unitree`의 sudo 권한 필요 |
| 자동 설치 대상 | 없는 `bubblewrap`, `v4l-utils`, `libc-bin`, `python3-numpy`. CUDA runtime 11.4 / `libnvinfer8` 8.5.2는 기존 APT 저장소에 맞는 버전이 있을 때만 추가 |
| 실행 패키지 포함 | C++ 실행파일, Python 실행 코드, IK용 Python 3.11 환경, 모델, DDS 등 패키지 내 라이브러리. 설치 후 실제 동적 라이브러리 연결 검사 |
| 외부 연결 | 설치 시 GitHub Release 다운로드와 필요한 APT 저장소 접속 가능 |
| Quest | 아래 Release APK 설치. G1과 서로 통신 가능한 네트워크에 연결 |
| 입력 / 카메라 | **Valleg**를 G1에 Bluetooth 연결(조이스틱 1개 인식), **Insta360 Link 2 Pro** USB 연결. 이 패키지는 Omni Connect 구성이 아님 |

설치기는 기존 패키지의 업그레이드·다운그레이드·재설치·삭제가 필요한 계획을 거부합니다. 누락된 모든 시스템 라이브러리를 임의로 설치하는 도구는 아니며, 기본 도구 누락·버전 불일치·기존 파일 충돌은 수동 확인이 필요합니다. OS/JetPack/PyTorch 전체를 설치해 주지는 않습니다.

## 2. 설치 + 자동 무모터 검사

```bash
cd ~
git clone https://github.com/Y1048/G1-Teleop-Runtime.git
cd G1-Teleop-Runtime
python3 setup_g1.py
```

이미 clone했다면 대신:

```bash
cd ~/G1-Teleop-Runtime
git pull --ff-only
python3 setup_g1.py
```

`sudo python3`로 시작하지 마세요. 필요한 단계에서 sudo 비밀번호를 요청합니다.

환경 확인 → Release 다운로드·해시 검사 → 없는 의존성/파일 설치 → 라이브러리 연결 검사 → **별도 격리 복사본에서 30초 시작·종료 검사**까지 자동으로 진행합니다. Release 파일을 따로 수동 다운로드할 필요는 없습니다. 기존 파일이 다르면 덮어쓰지 않고 중단합니다. 이전 버전이 이미 설치돼 있다면 실행파일·시작 스크립트 충돌로 중단할 수 있습니다. 이번 설치기는 기존 운용 환경을 자동 교체하는 업데이터가 아닙니다.

다음 문구가 나오면 자동 준비가 끝난 것입니다:

```text
INSTALL + ISOLATED LIFECYCLE COMPLETE. Motor controller NOT executed.
```

실패하면 출력된 `~/g1-setup-.../` 기록을 확인하고 해결한 뒤 진행하세요. 이 검사는 Valleg 대기 모형을 사용하며 실제 Quest·카메라·LowState·모터·TensorRT 추론 검증을 대신하지 않습니다.

## 3. Quest APK 설치 (PC에서 처음 한 번)

[Quest APK 다운로드 — apktest202610151729.apk](https://github.com/Y1048/G1-Teleop-Runtime/releases/download/v0.1.1-pre.20261021/apktest202610151729.apk)

기존 전달용 APK를 재빌드 없이 제공합니다. Unity Editor는 필요하지 않습니다. G1 설치 스크립트가 Quest에 APK를 자동 설치하지는 않습니다.

1. Quest의 개발자 모드·손 추적을 켭니다. USB로 PC에 연결하고 헤드셋에서 USB 디버깅을 허용합니다.
2. PC에 [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools)를 받아 압축을 풉니다.
3. APK를 `adb.exe`와 같은 폴더에 놓고, 그 폴더의 Windows PowerShell에서 실행합니다.

```powershell
.\adb.exe devices
.\adb.exe install -r .\apktest202610151729.apk
```

`devices`에 `device`로 표시돼야 합니다. `unauthorized`면 헤드셋에서 디버깅을 허용하세요. 여러 기기가 연결돼 있으면 해당 Quest만 연결하거나 ADB의 `-s SERIAL` 옵션으로 지정합니다. `install -r`은 같은 앱을 업데이트하며 서명이 다르면 중단됩니다. 기존 앱을 임의로 삭제하지 마세요.

Quest의 **알 수 없는 출처 → G1 Teleop 202610151729** 앱을 한 번 실행한 뒤, 다음 명령의 `G1_IP_HERE`를 **Quest에서 접근 가능한 G1 주소**로 바꿔 실행합니다.

```powershell
.\adb.exe shell "echo G1_IP_HERE > /sdcard/Android/data/kr.kaeri.g1quest3steleop/files/g1_pc_host.txt"
.\adb.exe shell am force-stop kr.kaeri.g1quest3steleop
.\adb.exe shell am start -n kr.kaeri.g1quest3steleop/com.unity3d.player.UnityPlayerActivity
```

주소 파일이 없으면 이 APK는 기존 PC 주소 `192.168.10.199`를 사용하므로 **G1 단독 실행 전 반드시 설정**하세요. G1 주소가 바뀌면 이 설정도 변경합니다. USB는 APK 설치·설정용이며 실행 중 통신은 네트워크로 이뤄집니다.

APK SHA-256:

```text
28591c1fde91110f6ecfee5694ab541fe8787ed6b313d81a1163eba7a23630c7
```

전달본 식별: `apktest202610151729.apk`와 위 SHA-256을 사용합니다. 비공개 개발 저장소에 접근할 필요가 없습니다. APK 압축 무결성과 전달본 해시를 확인했으며, 이번 작업에서 Quest 설치·착용 검사는 하지 않았습니다.

## 4. Quest IP 자동 탐지

G1의 주소 확인:

```bash
ip -br addr
```

Quest APK의 서버 주소에 **Quest에서 접근 가능한 이 G1의 IP**를 입력하고 APK를 실행하세요. Wi-Fi 연결이라면 보통 G1의 `wlan0` 주소를 사용합니다. 다른 G1에서도 주소가 같다고 가정하지 마세요.

```bash
cd ~/G1-Teleop-Runtime
python3 discover_quest.py
```

최대 60초 동안 UDP 5020으로 들어오는 APK 입력을 확인하고 **Quest IP와 아래 실행 명령을 출력한 뒤 종료**합니다. 모터는 자동 실행하지 않습니다. 포트 사용 중이면 기존 teleop를 정상 종료한 뒤 재시도하세요. Quest 주소가 바뀌면 다시 탐지합니다.

## 5. 실제 장치 연결 검사 — 로봇 모터 제외

아래 `QUEST_IP_HERE`를 탐지 결과로 바꾸거나, 탐지 프로그램이 출력한 명령을 복사하세요.

```bash
cd /home/unitree/sangmyeong_g1
NO_MOTORS=1 ./start_all.sh QUEST_IP_HERE
```

Quest 화면·양손 입력/IK·Valleg 입력·카메라와 오류 로그를 확인하세요. **C++ actuator만 생략하며 카메라 PTZ는 움직일 수 있습니다.** 다른 제어기가 실행 중인 상태에서는 시작하지 마세요.

검사가 끝나면 같은 터미널에서 **Enter → `all stopped` 확인** 후 다음 단계를 진행합니다.

## 6. 실제 모터 실행 — 사용자가 직접

연결 검사와 해당 GROOT 제어기의 시작 자세·모드 등 운용 조건을 확인한 뒤 실행하세요.

```bash
cd /home/unitree/sangmyeong_g1
NO_MOTORS=0 ./start_all.sh QUEST_IP_HERE
```

**5초 카운트다운 후 실제 모터가 활성화됩니다.** 기존 `--supervisor-off`, `--accept-handoff-risk` 옵션을 유지합니다. 설치 성공만으로 새 G1의 균형·추종 성능이 검증되는 것은 아닙니다.

정상 종료는 같은 터미널에서 **Enter → `all stopped` 확인**입니다. 현재 구현은 actuator가 **damping 후 종료**하며 자동 Regular/AI 복귀나 모터 힘 유지를 보장하지 않습니다. 창의 X 버튼을 정상 종료로 사용하지 마세요.

## 로그와 현재 검증 범위

- 실행 로그: `/home/unitree/sangmyeong_g1/logs/run_날짜시간/`
- 최종 명령 observer: `/home/unitree/groot_onboard_runtime/logs/command_observer/`
- 설치 기록: 설치기가 출력한 `~/g1-setup-.../`

기존 G1에서 별도 격리 복사본의 시작·ACK·종료와 설치 사전검사를 확인했습니다. 새 G1 전체 실설치·모터 동작과 실제 Quest IP 탐지는 아직 미검증입니다. 2026-10-20 G1에서 탐지 프로그램 시작·입력 없이 timeout 종료·UDP 5020 반환은 확인했습니다.

상세 자료: [자동 설치](docs/AUTO_SETUP_KO.md) · [Quest 탐지](docs/QUEST_AUTO_IP_KO.md) · [검증 기록](docs/ON_G1_VALIDATION_20261020.md) · [라이선스 고지](docs/LICENSING.md) · [실행 패키지 Release](https://github.com/Y1048/G1-Teleop-Runtime/releases/tag/v0.1.1-pre.20261021)

핵심 C++/Unity 원문 소스는 포함하지 않지만 역공학 불가능을 보장하지는 않습니다.
