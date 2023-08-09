from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication
import sys
import cv2 as cv
from datetime import datetime
import threading
import qimage2ndarray
import time
import pyaudio
import wave
import moviepy.editor as moviepy
import os


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.__init_ui__()
        self.primary_screen = QApplication.primaryScreen()
        self.audio = pyaudio.PyAudio()
        self.devie_info = self.__get_device_info_by_name__("立体混合音")
        self.running = False

    def __del__(self):
        self.audio.terminate()

    def __init_widget__(self):
        widget = QtWidgets.QWidget(self)
        vbox_layout = QtWidgets.QVBoxLayout()
        vbox_layout.setContentsMargins(260, 210, 260, 210)
        start_button = QtWidgets.QPushButton(self)
        start_button.setText("录制屏幕")
        start_button.clicked.connect(self.__start_capture__)
        vbox_layout.addWidget(start_button)
        end_button = QtWidgets.QPushButton(self)
        end_button.setText("结束录制")
        end_button.clicked.connect(self.__stop_capture__)
        vbox_layout.addWidget(end_button)
        label = QtWidgets.QLabel(self)
        label.setLayoutDirection(QtCore.Qt.LeftToRight)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setText("录制时请隐藏本窗口")
        vbox_layout.addWidget(label)
        widget.setLayout(vbox_layout)
        self.run_label = QtWidgets.QLabel(self)
        self.run_label.setText("")
        vbox_layout.addWidget(self.run_label)
        self.setCentralWidget(widget)

    def __init_ui__(self):
        self.__init_widget__()
        self.setWindowTitle("Recorder")
        self.resize(703, 588)

    def __get_device_info_by_name__(self, device_name: str):
        for index in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(index)
            if info["name"].find(device_name) != -1:
                return info
        return dict()

    def __record_video__(self, filename: str, fps: float, sync_event: threading.Event, exit_event: threading.Event):
        hwnd = QApplication.desktop().winId()

        width = self.primary_screen.size().width()
        height = self.primary_screen.size().height()
        video_out = cv.VideoWriter(filename, cv.VideoWriter_fourcc(
            *"XVID"), fps, (width, height), True)

        sync_event.wait()
        while True:
            if exit_event.isSet():
                break

            start_time = time.time()
            img = self.primary_screen.grabWindow(hwnd).toImage()
            frame = qimage2ndarray.rgb_view(img)
            video_out.write(cv.cvtColor(frame, cv.COLOR_RGB2BGR))
            end_time = time.time()
            if (1.0 / fps + start_time > end_time):
                time.sleep(1.0 / fps + start_time - end_time)

        video_out.release()

    def __record_audio__(self, filename: str, sync_event: threading.Event, exit_event: threading.Event):
        # 录音参数
        device_index = self.devie_info["index"]
        chunk_size = 1024
        format = pyaudio.paInt16
        channels = self.devie_info["maxInputChannels"]
        rate = int(self.devie_info["defaultSampleRate"])

        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(self.audio.get_sample_size(format))
            wf.setframerate(rate)

            # 打开音频流
            stream = self.audio.open(format=format,
                                     channels=channels,
                                     rate=rate,
                                     input=True,
                                     input_device_index=device_index,
                                     frames_per_buffer=chunk_size)

            sync_event.wait()
            while True:
                if exit_event.isSet():
                    break
                wf.writeframes(stream.read(chunk_size))

            # 停止录制
            stream.stop_stream()
            stream.close()

    def __fusion_video_and_audio__(self, outname: str, videoname: str, audioname: str):
        audio = moviepy.AudioFileClip(audioname)
        video = moviepy.VideoFileClip(videoname)

        video.set_audio(audio).write_videofile(outname)

        audio.close()
        video.close()

    def __start_capture__(self):
        self.showMinimized()
        self.basename = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
        self.sync_event = threading.Event()
        self.exit_event = threading.Event()
        self.video_thread = threading.Thread(
            target=self.__record_video__, args=(self.basename + ".avi", 25, self.sync_event, self.exit_event))
        self.audio_thread = threading.Thread(
            target=self.__record_audio__, args=(self.basename + ".wav", self.sync_event, self.exit_event))
        self.video_thread.start()
        self.audio_thread.start()
        self.sync_event.set()
        self.running = True
        print('开始录制！')
        self.run_label.setText("录制中...")

    def __stop_capture__(self):
        if self.running:
            self.exit_event.set()
            self.video_thread.join()
            self.audio_thread.join()
            self.__fusion_video_and_audio__(
                self.basename + ".mp4", self.basename + ".avi", self.basename + ".wav")
            os.remove(self.basename + ".avi")
            os.remove(self.basename + ".wav")
            self.run_label.setText(
                "录制结束\n录制文件名:{}".format(self.basename + ".mp4"))
            self.running = False
            print("结束录制！")
        else:
            self.run_label.setText("视频还未录制！")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    sys.exit(app.exec_())
