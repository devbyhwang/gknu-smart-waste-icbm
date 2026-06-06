# UML Diagrams

PNG versions:

- [Class Diagram](images/class-diagram.png)
- [Code Flow Sequence Diagram](images/code-flow-sequence.png)
- [Full Bin Exception Sequence Diagram](images/full-bin-exception-sequence.png)
- [User Sequence Diagram](images/user-sequence.png)

## Code Flow Sequence Diagram

```mermaid
sequenceDiagram
    participant Main as main()
    participant Camera as CameraManager
    participant Classifier as WasteClassifier
    participant Engine as InferenceEngine
    participant Output as OutputM
    participant Display as DisplayC
    participant Audio as AudioC
    participant Motor as MotorC
    participant Bluetooth as BluetoothC
    participant BLE as EmbeddedBleServer

    Main->>Camera: CameraManager(...)
    Main->>Engine: InferenceEngine(...)
    Main->>Output: OutputM()
    Main->>Bluetooth: connect()
    Bluetooth->>BLE: start()
    Main->>Classifier: WasteClassifier(...)
    Main->>Classifier: run()

    loop Camera loop
        Classifier->>Camera: get_frame()
        Camera-->>Classifier: frame

        Classifier->>Output: refreshSensorStatus()
        Output->>Output: collectFillLevels()
        Output->>Output: collectFullBins(fill_levels)
        Output->>Display: showSensorSnapshot(fill_levels, full_bins, message)
        Output->>Bluetooth: sendEvent("BIN_FULL", message)
        Bluetooth->>BLE: send_event(event, message)

        Classifier->>Engine: predict(frame)
        Engine-->>Classifier: label, confidence, bbox

        Classifier->>Classifier: validate(label, confidence)

        alt Classification passed
            Classifier->>Output: handleClassification(result)
            Output->>Output: collectFillLevels()
            Output->>Output: collectFullBins(fill_levels)

            alt Bin available
                Output->>Display: showClassificationStatus(label, confidence, fill_levels, full_bins, message)
                Output->>Audio: play_tts(label)
                Output->>Motor: process_item(label)
            else Bin full
                Output->>Display: showBinFullWarning(message, fill_levels, full_bins)
                Output->>Audio: playEffect(WARNING)
                Output->>Bluetooth: sendEvent("BIN_FULL", message)
                Bluetooth->>BLE: send_event(event, message)
            end
        else Classification not passed
            Classifier->>Classifier: update decision state
        end

        Classifier->>Classifier: draw camera overlay
    end
```

## Full Bin Exception Sequence Diagram

```mermaid
sequenceDiagram
    participant Classifier as WasteClassifier
    participant Output as OutputM
    participant Sensor as SensorC
    participant Display as DisplayC
    participant Audio as AudioC
    participant Bluetooth as BluetoothC
    participant BLE as EmbeddedBleServer
    participant Motor as MotorC

    Classifier->>Output: handleClassification(result)

    Output->>Sensor: checkFillLevel()
    Sensor-->>Output: fill_level

    Output->>Sensor: isFull()
    Sensor-->>Output: full_status

    Output->>Output: collectFullBins(fill_levels)

    alt full_bins exists
        Output->>Display: showBinFullWarning(message, fill_levels, full_bins)
        Output->>Audio: playEffect(WARNING)
        Output->>Bluetooth: sendEvent("BIN_FULL", message)
        Bluetooth->>BLE: send_event(event, message)
        Output-->>Classifier: return without motor action
    else no full bins
        Output->>Display: showClassificationStatus(label, confidence, fill_levels, full_bins, message)
        Output->>Audio: play_tts(label)
        Output->>Motor: process_item(label)
    end
```

## Class Diagram

```mermaid
classDiagram
    class WasteType {
        <<enumeration>>
        CAN
        PLASTIC
        GLASS
        PAPER
        UNKNOWN
    }

    class SoundType {
        <<enumeration>>
        SUCCESS
        WARNING
    }

    class ClassificationResult {
        +WasteType label
        +float confidence
    }

    class HandleClassificationResult {
        <<abstract>>
        +handleClassification(result)
    }

    class CameraManager {
        +int index
        +int width
        +int height
        +int fps
        +proc
        +bytes raw_bytes
        +get_frame()
        +release()
    }

    class InferenceEngine {
        +model
        +float conf_thres
        +int imgsz
        +str device
        +predict(frame)
    }

    class WasteClassifier {
        +camera
        +InferenceEngine engine
        +HandleClassificationResult handler
        +int max_count
        +int interval_ms
        +float min_confidence
        +img_dir
        +last_label
        +int consecutive_count
        +validate(label, conf)
        +map_to_enum(label_str)
        +run(window_name)
    }

    class OutputM {
        +DisplayC display
        +AudioC audio
        +MotorC servo
        +dict sensors
        +SensorC sensor
        +BluetoothC bluetooth
        +collectFillLevels()
        +collectFullBins(fill_levels)
        +refreshSensorStatus()
        +handleClassification(result)
        +handleException()
    }

    class DisplayC {
        +bool isScreenOn
        +str window_name
        +str img_dir
        +selected_label
        +confidence
        +dict fill_levels
        +set full_bins
        +str message
        +render_frame()
        +showClassificationStatus(label, confidence, fill_levels, full_bins, message)
        +showWarning(message)
        +showBinFullWarning(message, fill_levels, full_bins)
        +showSensorSnapshot(fill_levels, full_bins, message)
        +refreshScreen()
    }

    class AudioC {
        +int volume
        +dict category
        +dict audio_files
        +str effect_path
        +playEffect(soundType)
        +play_voice(category_name)
        +play_tts(text)
    }

    class MotorC {
        +dict ANGLE_MAP
        +int currentAngle
        +int bottom_pin
        +int top_pin
        +int pinNumber
        +float move_delay
        +bottom_servo
        +top_servo
        +int bottom_angle
        +int top_angle
        +list command_log
        +reset_motors()
        +process_item(received_value)
    }

    class SensorC {
        +float fillThreshold
        +float empty_bin_dist
        +sensor
        +checkFillLevel()
        +isFull()
        +readAnalogValue()
    }

    class BluetoothC {
        +bool isConnected
        +server
        +BleNotifier notifier
        +connect()
        +sendEvent(event, message)
    }

    class EmbeddedBleServer {
        +str name
        +str service_uuid
        +str char_uuid
        +PiBleNotifyTransport transport
        +PiBleNotifier notifier
        +loop
        +thread
        +server
        +bool is_running
        +start(timeout)
        +send_event(event, message)
        +stop()
    }

    class PiBleNotifyTransport {
        +str service_uuid
        +str char_uuid
        +server
        +set_server(server)
        +send(payload)
    }

    class PiBleNotifier {
        +PiBleNotifyTransport transport
        +notify(event, message)
    }

    class BleNotification {
        +str event
        +str message
        +bytes payload
    }

    class JsonPayloadBuilder {
        +build(event, message)
    }

    class BleNotifier {
        <<abstract>>
        +notify(event, message)
    }

    class MockBleNotifier {
        +JsonPayloadBuilder payload_builder
        +list notifications
        +notify(event, message)
    }

    HandleClassificationResult <|.. OutputM
    BleNotifier <|.. MockBleNotifier

    WasteClassifier o-- CameraManager
    WasteClassifier o-- InferenceEngine
    WasteClassifier o-- HandleClassificationResult
    WasteClassifier ..> ClassificationResult
    WasteClassifier ..> WasteType

    OutputM *-- DisplayC
    OutputM *-- AudioC
    OutputM *-- MotorC
    OutputM *-- BluetoothC
    OutputM *-- SensorC
    OutputM ..> ClassificationResult
    OutputM ..> WasteType
    OutputM ..> SoundType

    DisplayC ..> WasteType
    AudioC ..> SoundType
    MotorC ..> WasteType

    BluetoothC *-- EmbeddedBleServer
    BluetoothC o-- BleNotifier
    BluetoothC o-- MockBleNotifier

    EmbeddedBleServer *-- PiBleNotifyTransport
    EmbeddedBleServer *-- PiBleNotifier
    PiBleNotifier o-- PiBleNotifyTransport

    MockBleNotifier *-- JsonPayloadBuilder
    MockBleNotifier *-- BleNotification
```
