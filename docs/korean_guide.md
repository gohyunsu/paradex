# Paradex 한국어 가이드

이 문서는 Paradex를 처음 보는 사람이 전체 시스템을 빠르게 이해하고,
어떤 순서로 setup과 validation을 진행해야 하는지 잡기 위한 한국어
요약이다. 세부 API 시그니처는 영어 API 문서를 기준으로 본다.

---

## 1. Paradex가 하는 일

Paradex는 로봇 조작 실험을 위한 분산 멀티카메라 비전 + 로봇 제어
프레임워크다. 한 줄로 말하면 다음 일을 한다.

1. 여러 capture PC에 붙은 카메라를 main PC에서 원격으로 켜고 끈다.
2. 카메라 영상, 로봇 관절 상태, 손 상태, teleop 입력, 타임스탬프를 한
   session으로 저장한다.
3. 저장된 raw 데이터를 보정하고, 동기화하고, overlay와 mask, 3D 재구성,
   object pose 같은 downstream 결과로 가공한다.
4. perception 결과가 로봇 좌표계에서 말이 되는지 확인하고, 실제 로봇 실행
   전에 visualizer와 validation script로 점검한다.

Paradex는 단일 모델이 아니라 실험 장비 전체를 묶는 glue layer다. 카메라,
로봇, NAS, calibration, processing, visualization을 같은 파일 구조와 실행
규약 안에서 연결한다.

---

## 2. 전체 구조

```text
Main PC
  ├─ capture PC들을 SSH로 실행
  ├─ ZMQ command/data channel 관리
  ├─ calibration, processing, inference orchestration
  └─ robot controller / visualizer 실행

Capture PC
  ├─ FLIR camera daemon 실행
  ├─ 카메라 hardware lifecycle 소유
  ├─ local raw video 저장
  └─ telemetry/progress를 main PC로 전송

NAS / shared_data
  ├─ raw session
  ├─ camera parameters
  ├─ processed videos and masks
  ├─ object reconstruction outputs
  └─ validation artifacts
```

핵심 원칙은 main PC가 카메라를 직접 열지 않는다는 점이다. main PC는
`remote_camera_controller`를 통해 capture PC daemon에 명령을 보내고,
capture PC daemon이 실제 FLIR/PySpin camera를 소유한다.

---

## 3. 주요 구성 요소

| 구성 요소 | 위치 | 역할 |
|-----------|------|------|
| Camera daemon | `src/camera/server_daemon.py` | capture PC에서 카메라를 소유하고 ZMQ 명령을 받는다. |
| Remote camera controller | `paradex/io/camera_system/remote_camera_controller.py` | main PC에서 여러 capture PC daemon을 제어한다. |
| Capture-PC transport | `paradex/io/capture_pc/` | SSH launch, command channel, telemetry/data channel. |
| Dataset acquisition | `src/dataset_acquisition/`, `paradex/dataset_acqusition/` | 카메라/로봇/손/teleop stream을 session으로 저장한다. |
| Processing framework | `paradex/process/` | `Job`, `Ctx`, `run_jobs`, `run_distributed` 기반 batch 처리. |
| Video processor | `paradex/video/` | raw video undistort, dropped-frame correction, H.264 encode, NAS upload. |
| Image tools | `paradex/image/` | `ImageDict`, undistort, merge, projection, ArUco/Charuco 처리. |
| Robot layer | `paradex/robot/`, `paradex/io/robot_controller/` | URDF/FK/planning/controller 연결. |
| Visualization | `paradex/visualization/` | Viser/Open3D 기반 scene, robot, overlay 확인. |
| Validation scripts | `src/validate/` | 실험 전 subsystem smoke test. |

주의: `dataset_acqusition`의 오타는 기존 코드 호환을 위한 의도된 이름이다.
고치지 않는다.

---

## 4. 실행 흐름

일반적인 실험/데이터 생성 흐름은 아래 순서로 본다.

```text
system/current 설정
  -> camera daemon 준비
  -> capture-PC transport 확인
  -> camera acquisition 확인
  -> robot / hand / teleop 연결 확인
  -> capture session 실행
  -> raw data processing
  -> pose / grasp / overlay validation
  -> robot execution
```

각 단계는 다음 단계의 입력을 만든다. 예를 들어 camera-to-robot calibration이
바뀌면 pose estimation, grasp transform, robot overlay를 다시 확인해야 한다.

---

## 5. 설정 파일

`system/current/`는 실행 중인 머신에 맞는 local config다. git에 들어가는
공통 코드와 다르게, 이 디렉터리는 장비별 설정을 가리킨다.

주요 파일:

| 파일 | 의미 |
|------|------|
| `pc.json` | capture PC 이름, IP, camera serial list. |
| `network.json` | robot, signal generator, 기타 네트워크 장비 정보. |
| `camera.json` | serial별 gain, exposure, packet size 등 camera baseline 설정. |
| `charuco_info.json` | calibration board 정보. |

코드에서는 PC 목록이나 serial number를 hardcode하지 말고,
`paradex.utils.system`의 loader를 통해 읽는 것이 기본 규약이다.

---

## 6. Validation 순서

장비를 움직이기 전에 아래 순서대로 확인한다.

### 6.1 Offline sanity check

하드웨어 없이 빠르게 확인한다.

```bash
python src/validate/camera_system/hang_recovery_mock.py
python src/validate/camera_system/camera_sink_mock.py
python src/validate/camera_system/rcc_protocol_mock.py
python src/validate/visualizer/franka.py
```

통과 기준:

- mock script가 `PASS` 또는 `ALL PASSED`를 출력한다.
- Franka visualizer가 traceback 없이 Viser URL을 출력한다.

### 6.2 Main PC to capture PC transport

capture PC에 SSH로 client를 띄우고, telemetry가 main PC로 돌아오는지 본다.

```bash
python src/validate/data_sender/main.py
```

통과 기준:

- `capture1`, `capture2`, `capture3`, `capture5`, `capture6` 같은 PC 이름별로
  증가하는 `value`가 출력된다.

command channel까지 확인하려면:

```bash
python src/validate/command_sender/stream_remote.py
```

키보드 제어:

- `c`: capture PC client에 `start` 명령 전송
- `s`: `stop` 명령 전송
- `q`: 종료

### 6.3 Camera path

camera daemon과 실제 camera가 준비된 뒤 실행한다.

```bash
python src/validate/camera_system/remote_camera_controller.py

# Direct local/capture-PC checks only:
python src/validate/camera_system/camera_loader.py
python src/validate/camera_system/camera_reader.py
```

`remote_camera_controller.py`는 main PC에서 실행한다. `camera_loader.py`와
`camera_reader.py`는 카메라를 직접 소유한 capture PC 또는 local camera machine에서만
실행한다.

통과 기준:

- capture PC별 expected/detected camera count가 맞는다.
- 모든 camera serial의 frame id가 양수가 된다.
- `error`, `stalled`, `capture_interrupted`가 false/empty 상태다.

### 6.4 Sync / calibration

hardware trigger와 calibration data가 필요하다.

```bash
python src/validate/camera_system/sync_check.py --view
python src/validate/calibration/extrinsic_drift.py
python src/validate/calibration/compare_xarm_kinematic_calib.py --no_overlay
```

통과 기준:

- 여러 camera frame id가 tolerance 안에서 맞는다.
- drift와 residual이 이전 기준보다 커지지 않는다.

### 6.5 Robot / hand execution

실제 로봇이나 손을 움직일 수 있으므로 사람이 확인하면서 실행한다.

```bash
python src/validate/robot/xarm_base_wiggle.py
python src/validate/robot/inspire_left.py
python src/validate/robot/inspire_left_overlay.py
```

통과 기준:

- workspace가 비어 있고, emergency stop을 누를 수 있는 상태에서 실행한다.
- arm motion이 부드럽고, hand command와 sensor 값이 예상 범위에 있다.
- camera overlay에서 robot mesh가 실제 이미지와 맞는다.

---

## 7. Franka로 돌릴 때

현재 main line은 Franka FR3를 end-to-end로 바로 움직이는 상태는 아니다.
이미 있는 것은 URDF, visualizer, 일부 config entry, frame 정의다. 실제 제어를
하려면 `origin/vlm_dex` 쪽 Franka controller 관련 코드 중 필요한 부분만
선별 porting해야 한다.

현재 있는 것:

- `rsc/robot/franka.urdf`
- `src/validate/visualizer/franka.py`
- `system/*/network.json` 일부의 `franka` entry
- `paradex/transforms/coordinate.py`의 Franka frame 정의

아직 필요한 것:

- `paradex/io/robot_controller/franka_controller.py`
- `get_arm("franka")` factory support
- hand-eye capture/solve에서 `fr3_link8` end-effector link 지원
- ROS 2 / `franka_ros2` 기반 controller smoke test

자세한 내용은 {doc}`Franka FR3 Setup Notes <franka_setup>`를 본다.

---

## 8. 용어 정리

| 용어 | 의미 |
|------|------|
| Rig | 로봇 arm, hand, cameras, mounts, table, lights, capture PCs, NAS까지 포함한 전체 실험 장비 묶음. |
| Main PC | 실험을 orchestration하는 컴퓨터. capture PC와 robot/control process를 조율한다. |
| Capture PC | 카메라가 직접 연결된 컴퓨터. camera daemon과 raw video 저장을 담당한다. |
| Daemon | 계속 떠 있으면서 명령을 기다리는 service process. Paradex에서는 camera daemon이 대표적이다. |
| ZMQ | main PC와 capture PC 사이 command/data message를 보내는 네트워크 transport. |
| NAS | 여러 머신이 함께 쓰는 network storage. raw data와 processed output을 모은다. |
| Calibration | 카메라 내부 파라미터와 카메라-로봇 좌표 관계를 측정하는 과정. |
| C2R | camera-to-robot transform. 카메라 좌표의 점/pose를 로봇 좌표계로 바꾼다. |
| 6D pose | 물체의 3D 위치 + 3D 회전. |
| IK | inverse kinematics. 원하는 end-effector pose를 만들 수 있는 joint angle을 찾는 계산. |
| Sink | 이미 acquisition 중인 frame stream에서 어떤 output을 켤지 정하는 출력 경로. 예: video, stream, snapshot. |
| Job | `paradex.process`에서 처리할 하나의 작업 단위. 입력, 출력, done check, metadata를 가진다. |

---

## 9. 관련 문서

- {doc}`Camera System <camera_system>`
- {doc}`Robot Control <robot>`
- {doc}`Dataset Acquisition <dataset_acquisition>`
- {doc}`Video Processing <process>`
- {doc}`Franka FR3 Setup Notes <franka_setup>`
- {doc}`API Reference <autoapi/index>`
