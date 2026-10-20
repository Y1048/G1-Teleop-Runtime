# 새 G1 설치·실행 안내

현재 패키지는 **동일 환경의 G1에 옮길 실행 파일 묶음**이다. 자동 설치 프로그램이 아니다.
격리 환경의 시작·종료는 확인했지만, 새 G1의 실제 장치 연결과 모터 동작은 아직 확인하지 않았다.

아래는 **새 G1에 로그인한 `unitree` 계정의 터미널**에서 진행한다.
기존 G1이나 실행 중인 설치 위에 덮어쓰지 않는다.

## 1. 준비할 것

| 대상 | 조건 |
|---|---|
| G1 | Ubuntu 20.04.6, aarch64, JetPack 5.1.1 / L4T R35.3.1 |
| NVIDIA 환경 | CUDA 11.4, TensorRT 8.5.2, 커널 5.10.104-tegra |
| 시스템 Python | 3.8.10. IK용 Python 3.11은 패키지에 별도로 포함 |
| 인터페이스 | `eth0` |
| Quest | 기존에 사용하던 호환 APK 설치. **이번 Release에는 APK가 없다** |
| Valleg | 이 구성의 입력 장치. G1에 Bluetooth로 연결하고 조이스틱으로 인식되어야 함 |
| 카메라 | Insta360 Link 2 Pro 연결 및 v4l2 장치 인식 |
| 네트워크 | Quest와 G1이 서로 통신 가능한 주소·경로 |

이 패키지는 Omni Connect 기반 실행 구성으로 바꾼 것이 아니다.
OS 버전이 같아도 시스템 라이브러리, 권한, 장치 인식까지 같다는 뜻은 아니다.
TensorRT 엔진은 새 장비에서 로드 확인이 필요하며, 모터 실행으로 이를 대신 검사하지 않는다.

확인 명령:

```bash
cat /etc/os-release
uname -r
uname -m
cat /etc/nv_tegra_release
python3 --version
ip -br addr
dpkg-query -W 'libnvinfer*' 'cuda-cudart-*' 2>/dev/null
command -v curl rsync v4l2-ctl
python3 -c 'import numpy; print(numpy.__version__)'
```

필요한 시스템 도구가 없을 때만 관리자와 확인해 해당 패키지를 설치한다.
대표적인 누락 항목은 `curl`, `rsync`, `python3-numpy`, `v4l-utils`다.
`system-packages.txt` 전체를 설치하거나 시스템 Python/NVIDIA 환경을 업그레이드하지 않는다.

## 2. 다운로드·해시 확인

아래 `mkdir`가 이미 있는 폴더라는 오류를 내면 그대로 중단하고 새 이름을 사용한다.

```bash
mkdir "$HOME/g1_handoff_20261020"
cd "$HOME/g1_handoff_20261020"

base=https://github.com/Y1048/G1-Teleop-Runtime/releases/download/v0.1.0-pre.20261020
for file in \
  g1_core_binary_with_notices_20261020.tar.gz \
  native_source_build_supplement_20261020.tar.gz \
  remaining_native_build_records_20261020.tar.gz \
  validation_evidence.tar.gz \
  SHA256SUMS.txt
do
  curl --fail --location --output "$file" "$base/$file" || break
done

sha256sum -c SHA256SUMS.txt
```

**네 개 아카이브가 모두 `OK`여야 다음으로 진행한다.**
외부 인터넷을 쓸 수 없다면 다른 PC에서 동일 파일을 다운로드해 USB로 옮기고,
G1에서 같은 해시 검사를 한다.

## 3. 임시 폴더에 풀기

```bash
mkdir unpacked
tar -xzf g1_core_binary_with_notices_20261020.tar.gz -C unpacked
```

`unpacked/payload/`는 설치 경로의 복제본이다.
**여기 있는 `start_all.sh`를 실행하지 않는다.** 원래 절대경로를 참조한다.
나머지 보완 아카이브는 라이선스·출처 자료로 보관하며 `/`에 풀지 않는다.

## 4. 기존 파일 충돌 확인

현재 위치가 `~/g1_handoff_20261020`인지 확인하고 실행한다.
아래 검사는 읽기 전용이다. 이미 존재하는 파일이 동일하면 허용하고,
내용·종류·심볼릭 링크가 다르면 중단한다.

```bash
python3 - <<'PY'
from pathlib import Path
import os, filecmp
root = Path("unpacked/payload").resolve()
if not root.is_dir():
    raise SystemExit("payload not found")
conflicts = []
for src in root.rglob("*"):
    dst = Path("/") / src.relative_to(root)
    if not os.path.lexists(str(dst)):
        continue
    if src.is_symlink():
        same = dst.is_symlink() and os.readlink(src) == os.readlink(dst)
    elif src.is_dir():
        same = dst.is_dir() and not dst.is_symlink()
    else:
        same = dst.is_file() and not dst.is_symlink() and filecmp.cmp(src, dst, shallow=False)
    if not same:
        conflicts.append(str(dst))
for item in conflicts:
    print("CONFLICT:", item)
if conflicts:
    raise SystemExit("STOP: do not overwrite the existing installation")
print("PASS: no different existing files")
PY
```

`CONFLICT`가 하나라도 있으면 설치하지 않는다. 충돌 목록을 검토해 별도 이전 방안을 정한다.
특히 `easy-install.pth`, DDS 라이브러리, 기존 제어기 폴더를 무조건 교체하면 안 된다.

## 5. 충돌이 없는 새 장비에만 배치

이 단계부터 **새 G1에 파일을 설치한다.** 제어 프로그램이 실행 중이지 않아야 한다.
아래 복사는 기존 파일을 덮어쓰지 않지만, 충돌 검사를 생략해도 된다는 의미는 아니다.

```bash
sudo rsync -a --ignore-existing --chown=unitree:unitree \
  unpacked/payload/home/unitree/ /home/unitree/

sudo rsync -a --ignore-existing --chown=root:root \
  unpacked/payload/usr/local/lib/ /usr/local/lib/

sudo ldconfig
```

설치 결과를 manifest와 대조한다:

```bash
python3 - <<'PY'
import json, hashlib
from pathlib import Path
records = json.loads(Path("unpacked/manifest.json").read_text())
bad = []
for record in records:
    path = Path("/") / Path(record["path"]).relative_to("payload")
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1048576), b""):
                h.update(block)
        if h.hexdigest() != record["sha256"]:
            bad.append(str(path))
    except OSError:
        bad.append(str(path))
if bad:
    print("\n".join(bad))
    raise SystemExit("STOP: installed file mismatch")
print("PASS:", len(records), "manifest records")
PY
```

## 6. 모터 실행 전 검사

```bash
ldd /home/unitree/groot_command_observer_build_20261007_9dd21a6/build/groot_balance_actuator

cd /home/unitree/sangmyeong_g1
source ./env.sh
python3 -c 'import numpy, cv2, pygame, cyclonedds, unitree_sdk2py; print("imports OK")'

G1_BIMANUAL_ENGINE_ROOT="$PWD/runtime/python311/lib/python3.11/site-packages" \
  ./runtime/python311/bin/python3 -B \
  MuJoCo_G1_Controller/scripts/g1_bimanual_runtime.py --validate-only
```

`ldd`에 `not found`가 있거나 import/IK 검사가 실패하면 실행하지 않는다.
이 검사는 TensorRT 모델 추론과 모터 동작을 확인하는 검사는 아니다.

완전 격리 시작·종료를 반복하려면 저장소의 `docs/START_HERE.txt`를 따른다.
그 절차의 `--package`에는 이번에 푼 `~/g1_handoff_20261020/unpacked`를 사용하고,
`--destination`은 기존에 없는 새 경로로 지정한다.

## 7. Quest·Valleg·카메라를 연결해 무모터 통신 검사

- Quest APK의 서버 주소에는 **새 G1의 IP**를 넣는다.
- 시작 명령 인자에는 **Quest의 IP**를 넣는다. 둘을 바꾸지 않는다.
- Valleg는 G1에 연결한다. 현재 gateway는 정확히 한 개의 Valleg 조이스틱을 요구한다.
- 카메라도 G1에 연결한다.
- 다른 모터/상위제어기가 실행 중인 상태에서 검사하지 않는다.

아래 `QUEST_IP_HERE`를 실제 Quest 주소로 바꾼다.

```bash
cd /home/unitree/sangmyeong_g1
NO_MOTORS=1 ./start_all.sh QUEST_IP_HERE
```

이 명령은 **C++ actuator만 생략**한다. 실제 네트워크·LowState·카메라·PTZ·heading은
사용하므로 완전 격리 검사가 아니다. 카메라 PTZ는 움직일 수 있다.
이 단계는 이번 패키지의 새 G1에서 아직 검증하지 않았다.

Quest 화면, 양손 입력/IK, Valleg 입력, 카메라, 오류 로그를 확인한다.
종료는 같은 터미널에서 **Enter 한 번 → `all stopped` 확인**이다.

## 8. 실제 모터 실행

앞 단계와 새 G1의 모델 로드·제어기 시작 조건을 확인한 뒤 별도 실기 시험에서 사용한다.
현재 무모터 검증만으로 실기 안전성·균형·추종 성능이 검증된 것은 아니다.
로봇 시작 자세/모드는 해당 GROOT 제어기의 운용 조건을 따라야 하며 임의로 추정하지 않는다.

```bash
cd /home/unitree/sangmyeong_g1
NO_MOTORS=0 ./start_all.sh QUEST_IP_HERE
```

**5초 카운트다운 후 실제 모터가 활성화된다.**
기존 스크립트는 `--supervisor-off`, `--accept-handoff-risk` 등을 그대로 사용한다.
이 명령은 다운로드/설치 확인용 명령이 아니다.

정상 종료: 같은 터미널에서 **Enter 한 번**, `all stopped`까지 기다린다.
기존 구현은 actuator가 damping 후 정지하고 heading 등을 종료한다.
모터 힘 유지나 자동 Regular/AI 복귀를 보장하는 종료 방식이 아니다.
SSH 창의 X 버튼으로 닫는 것을 정상 종료로 사용하지 않는다.

## 로그

- 서버·IK·입력·heading·actuator: `/home/unitree/sangmyeong_g1/logs/run_날짜시간/`
- 명령 observer: `/home/unitree/groot_onboard_runtime/logs/command_observer/`
- heading 기록: `/home/unitree/groot_onboard_runtime/logs/`

패키지 안의 과거 README/검토 기록과 현재 저장소 상태가 다르면
현재 저장소의 `README.md`, `LICENSING.md`, `ON_G1_VALIDATION_20261020.md`를 우선한다.
