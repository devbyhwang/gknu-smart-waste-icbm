from .hardware import AudioC, BluetoothC, DisplayC, SensorC, ServoC, SoundType
from .models import ClassificationResult, HandleClassificationResult


class OutputM(HandleClassificationResult):
    def __init__(self):
        self.display = DisplayC()
        self.audio = AudioC()
        self.servo = ServoC()
        self.sensor = SensorC()
        self.bluetooth = BluetoothC()

    def checkBinFull(self):
        is_full = getattr(self.sensor, "isFull", None)
        if callable(is_full):
            return is_full()

        legacy = getattr(self.sensor, "is_full", None)
        if callable(legacy):
            return legacy()

        return False

    def handleException(self):
        warning_text = "출력 장치 처리 중 예외가 발생했습니다."
        show_warning = getattr(self.display, "showWarning", None)
        if callable(show_warning):
            show_warning(warning_text)
        else:
            legacy_warning = getattr(self.display, "show_warning", None)
            if callable(legacy_warning):
                legacy_warning(warning_text)

        play_effect = getattr(self.audio, "playEffect", None)
        if callable(play_effect):
            play_effect(SoundType.WARNING)

        send_event = getattr(self.bluetooth, "sendEvent", None)
        if callable(send_event):
            try:
                send_event("OUTPUT_EXCEPTION", warning_text)
            except Exception:
                pass

    def handleClassification(self, result: ClassificationResult):
        try:
            print(f"\n[OutputM] 결과 처리 시작: {result.label.value}")

            show_category = getattr(self.display, "showCategory", None)
            if callable(show_category):
                show_category(result.label.value, result.label.value)
            else:
                legacy_show_category = getattr(self.display, "show_category", None)
                if callable(legacy_show_category):
                    legacy_show_category(result.label.value)

            play_tts = getattr(self.audio, "playTTS", None)
            if callable(play_tts):
                play_tts(result.label.value)
            else:
                legacy_play_tts = getattr(self.audio, "play_tts", None)
                if callable(legacy_play_tts):
                    legacy_play_tts(result.label.value)

            rotate_to = getattr(self.servo, "rotateTo", None)
            if callable(rotate_to):
                rotate_to(90)
            else:
                legacy_rotate_to = getattr(self.servo, "rotate_to", None)
                if callable(legacy_rotate_to):
                    legacy_rotate_to(90)

            if self.checkBinFull():
                show_warning = getattr(self.display, "showWarning", None)
                if callable(show_warning):
                    show_warning("분류함이 가득 찼습니다!")
                else:
                    legacy_warning = getattr(self.display, "show_warning", None)
                    if callable(legacy_warning):
                        legacy_warning("분류함이 가득 찼습니다!")

                send_event = getattr(self.bluetooth, "sendEvent", None)
                if callable(send_event):
                    send_event("BIN_FULL", "분류함 비움 필요")
                else:
                    send_alert = getattr(self.bluetooth, "sendAlert", None)
                    if callable(send_alert):
                        send_alert("분류함 비움 필요")
                    else:
                        legacy_send_alert = getattr(self.bluetooth, "send_alert", None)
                        if callable(legacy_send_alert):
                            legacy_send_alert("분류함 비움 필요")
        except Exception:
            self.handleException()

    def handle_classification(self, result: ClassificationResult):
        return self.handleClassification(result)


class OutputManager(OutputM):
    pass
