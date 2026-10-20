# 자동 설치와 무모터 검사

새 G1에서 `unitree`로 로그인한 다음:

```bash
git clone https://github.com/Y1048/G1-Teleop-Runtime.git
cd G1-Teleop-Runtime
python3 setup_g1.py
```

이미 clone한 저장소가 있다면 중복 clone 대신 해당 폴더에서 `git pull --ff-only` 후 실행한다.
파일 배치에 필요한 `sudo` 비밀번호는 Linux가 요청한다. `sudo python3 setup_g1.py`로 시작하지 않는다.

스크립트가 자동으로 하는 일:

1. CPU·Ubuntu·L4T·CUDA·TensorRT·Python·eth0·필수 도구 및 기존 제어 프로세스 확인.
2. 격리 기능 작동 확인.
3. 실행 패키지와 두 라이선스 보완 아카이브 다운로드·SHA256 검사.
4. 별도 임시 경로에 안전하게 압축 해제.
5. 설치 경로 전체 대조: 다른 기존 파일/링크/파일 권한이 있으면 **설치 전에 중단**.
6. 없는 파일만 설치. 기존 동일 파일은 쓰기·chmod·chown하지 않는다.
7. 필요할 때 라이브러리 캐시 갱신, 설치 파일 및 C++ 동적 라이브러리 연결 확인.
8. 별도 복사본에서 C++ actuator를 제외하고 네트워크·장치·홈을 격리해 30초 시작·통신 검사.
9. Enter 종료 요청, ready/ACK/종료 기록 및 설치 파일 보존 확인.

**모터 실행은 포함하지 않는다.** Valleg는 값을 보내지 않는 대기 모형이다.
실제 Quest·카메라·LowState·Valleg·모터 연동과 TensorRT 추론을 완료했다고 표시하지 않는다.
실제 장비 입력 검사는 이 자동 검사 이후 별도 단계다.

설치 없이 확인하려면:

```bash
python3 setup_g1.py --check-only
```

다운로드 파일이 USB 등에 있다면:

```bash
python3 setup_g1.py --archive-dir /실제/아카이브/폴더
```

해당 폴더에는 `artifacts.json`의 실행 패키지 및 두 native 보완 아카이브가 있어야 한다.

## 중단됐을 때

로그·전달 자료·설치 기록은 출력된 `~/g1-setup-.../`에 남는다.
OS/드라이버/Python 패키지는 자동 변경하지 않는다. 필수 도구가 없으면 필요한 이름을 출력한다.
충돌 시 `preflight.json`, 설치 중 오류 시 `install-receipt.json`을 확인한다.
일부 새 파일을 설치한 뒤 실패하면 그 파일을 자동 삭제하지 않는다.
기존 파일을 보호하므로, 내용이 다른 파일을 발견하면 이를 자동 수정하거나 덮어쓰지 않는다.
재실행은 동일 파일을 보존하며 진행하지만, 중간에 잘린 파일은 충돌로 중단한다.

## 검증 범위 — 2026-10-20

- 기존 G1 Python 3.8에서 임시 가상 설치 루트 대상 자동 테스트 **9/9 통과**.
- 실제 실행 아카이브를 사용한 기존 G1 `--check-only` **통과**.
- 실제 G1에서 별도 namespace의 server/IK/heading 시작·ACK·Enter 종료는 앞선 검사에서 확인.
- 새 G1의 실제 `/home/unitree`, `/usr/local/lib`에 이 자동 설치기로 설치하는 전체 경로는 아직 미실행.
- 기존 운용 설치는 수정하지 않았다.

사전검사와 fixture 검사는 새 장비의 실제 운용 성공을 보장하지 않는다.
