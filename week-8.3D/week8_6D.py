import os
import time
import csv
import base64
import threading
import queue
import traceback
from datetime import datetime

import cv2

from arduino_iot_cloud import ArduinoCloudClient

from dash import Dash, dcc, html, Input, Output, no_update
import plotly.graph_objects as go


DEVICE_ID = "4e207963-8877-4378-bfb1-04c7d078ad82"
SECRET_KEY = "DuSEgXjKbJIBX@78muu#tkUCm"

SAVE_FOLDER = "week-8.3D/captured_data"
os.makedirs(SAVE_FOLDER, exist_ok=True)

SEGMENT_DURATION = 10
sequence_number = 1


data_queue = queue.Queue()

segment_buffer = []
segment_lock = threading.Lock()


latest_x = None
latest_y = None
latest_z = None

new_x = False
new_y = False
new_z = False


latest_segment = []
latest_image_src = None
latest_saved_name = "Waiting for first 10-second segment..."

def process_combined_data():

    global latest_x, latest_y, latest_z
    global new_x, new_y, new_z

    if new_x and new_y and new_z:

        now = datetime.now()

        sample = {
            "time": now.strftime("%H:%M:%S.%f")[:-3],
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "x": latest_x,
            "y": latest_y,
            "z": latest_z
        }

        # Send sample to live graph
        data_queue.put(sample)

        # Save sample into current 10-second segment
        with segment_lock:
            segment_buffer.append(sample.copy())

        new_x = False
        new_y = False
        new_z = False

def on_accelerometer_x_changed(client, value):

    global latest_x, new_x

    latest_x = value
    new_x = True

    process_combined_data()


def on_accelerometer_y_changed(client, value):

    global latest_y, new_y

    latest_y = value
    new_y = True

    process_combined_data()


def on_accelerometer_z_changed(client, value):

    global latest_z, new_z

    latest_z = value
    new_z = True

    process_combined_data()

def start_arduino_cloud():

    try:

        print("Starting Arduino Cloud client...")

        client = ArduinoCloudClient(
            device_id=DEVICE_ID,
            username=DEVICE_ID,
            password=SECRET_KEY
        )

        client.register(
            "accelerometer_x",
            value=None,
            on_write=on_accelerometer_x_changed
        )

        client.register(
            "accelerometer_y",
            value=None,
            on_write=on_accelerometer_y_changed
        )

        client.register(
            "accelerometer_z",
            value=None,
            on_write=on_accelerometer_z_changed
        )

        client.start()

    except Exception:

        traceback.print_exc()

def save_segment_csv(segment, csv_path):

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "timestamp",
            "accelerometer_x",
            "accelerometer_y",
            "accelerometer_z"
        ])

        for sample in segment:

            writer.writerow([
                sample["timestamp"],
                sample["x"],
                sample["y"],
                sample["z"]
            ])

def capture_webcam_image(camera, image_path):

    success, frame = camera.read()

    if not success:

        print("ERROR: Could not capture webcam image.")
        return None

    cv2.imwrite(image_path, frame)

    success, encoded_image = cv2.imencode(
        ".jpg",
        frame
    )

    if not success:
        return None

    encoded_string = base64.b64encode(
        encoded_image
    ).decode("utf-8")

    return (
        "data:image/jpeg;base64,"
        + encoded_string
    )

def segment_capture_worker():

    global sequence_number
    global latest_segment
    global latest_image_src
    global latest_saved_name

    print("Starting webcam...")

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print(
            "ERROR: Cannot open webcam. "
            "Check macOS camera permissions."
        )

        return

    print("Webcam started successfully.")

    while True:

        time.sleep(SEGMENT_DURATION)

        with segment_lock:

            current_segment = segment_buffer.copy()
            segment_buffer.clear()

        if len(current_segment) == 0:

            print(
                "No accelerometer data received "
                "during this 10-second period."
            )

            continue

        file_timestamp = datetime.now().strftime(
            "%Y%m%d%H%M%S"
        )

        base_filename = (
            f"{sequence_number}_{file_timestamp}"
        )

        csv_path = os.path.join(
            SAVE_FOLDER,
            base_filename + ".csv"
        )

        image_path = os.path.join(
            SAVE_FOLDER,
            base_filename + ".jpg"
        )

        save_segment_csv(
            current_segment,
            csv_path
        )

        image_src = capture_webcam_image(
            camera,
            image_path
        )

        latest_segment = current_segment

        if image_src is not None:
            latest_image_src = image_src

        latest_saved_name = base_filename

        print(
            f"Segment {sequence_number} saved | "
            f"{len(current_segment)} samples | "
            f"{base_filename}"
        )

        sequence_number += 1
        
app = Dash(__name__)

live_figure = go.Figure()

live_figure.add_trace(
    go.Scatter(
        x=[],
        y=[],
        mode="lines",
        name="Accelerometer X"
    )
)

live_figure.add_trace(
    go.Scatter(
        x=[],
        y=[],
        mode="lines",
        name="Accelerometer Y"
    )
)

live_figure.add_trace(
    go.Scatter(
        x=[],
        y=[],
        mode="lines",
        name="Accelerometer Z"
    )
)

live_figure.update_layout(
    title="Live Smartphone Accelerometer Data",
    xaxis_title="Time",
    yaxis_title="Acceleration",
    hovermode="x unified",
    yaxis=dict(
        range=[-1.5, 1.5]
    )
)


live_figure.update_xaxes(
    nticks=10
)

segment_figure = go.Figure()


segment_figure.update_layout(
    title="Latest 10-Second Accelerometer Segment",
    xaxis_title="Time",
    yaxis_title="Acceleration",
    yaxis=dict(
        range=[-1.5, 1.5]
    )
)

app.layout = html.Div([

    html.H1(
        "SIT225 Activity Data Capture Dashboard",
        style={
            "textAlign": "center"
        }
    ),

    html.P(
        "Smartphone Accelerometer + Webcam Activity Capture",
        style={
            "textAlign": "center"
        }
    ),

    html.Hr(),

    html.H2(
        "Live Accelerometer Data"
    ),

    dcc.Graph(
        id="live-accelerometer-graph",
        figure=live_figure
    ),

    html.H2(
        "Latest 10-Second Segment"
    ),

    html.Div(
        id="segment-status",
        children="Waiting for data..."
    ),

    dcc.Graph(
        id="segment-graph",
        figure=segment_figure
    ),

    html.H2(
        "Captured Activity Image"
    ),

    html.Img(
        id="activity-image",
        style={
            "width": "640px",
            "maxWidth": "100%",
            "border": "1px solid black"
        }
    ),

    dcc.Interval(
        id="live-update",
        interval=100,
        n_intervals=0
    ),

    dcc.Interval(
        id="segment-update",
        interval=1000,
        n_intervals=0
    )

])

@app.callback(
    Output(
        "live-accelerometer-graph",
        "extendData"
    ),
    Input(
        "live-update",
        "n_intervals"
    )
)

def update_live_graph(n):

    samples = []

    while not data_queue.empty():

        try:

            samples.append(
                data_queue.get_nowait()
            )

        except queue.Empty:

            break

    if len(samples) == 0:

        return no_update

    timestamps = [
        sample["time"]
        for sample in samples
    ]

    x_values = [
        sample["x"]
        for sample in samples
    ]

    y_values = [
        sample["y"]
        for sample in samples
    ]

    z_values = [
        sample["z"]
        for sample in samples
    ]

    return (
        {
            "x": [
                timestamps,
                timestamps,
                timestamps
            ],

            "y": [
                x_values,
                y_values,
                z_values
            ]
        },

        [0, 1, 2],

        200
    )

@app.callback(
    Output(
        "segment-graph",
        "figure"
    ),
    Output(
        "activity-image",
        "src"
    ),
    Output(
        "segment-status",
        "children"
    ),
    Input(
        "segment-update",
        "n_intervals"
    )
)

def update_latest_segment(n):

    if len(latest_segment) == 0:

        return (
            no_update,
            no_update,
            latest_saved_name
        )

    timestamps = [
        sample["time"]
        for sample in latest_segment
    ]

    x_values = [
        sample["x"]
        for sample in latest_segment
    ]

    y_values = [
        sample["y"]
        for sample in latest_segment
    ]

    z_values = [
        sample["z"]
        for sample in latest_segment
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=x_values,
            mode="lines",
            name="X"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=y_values,
            mode="lines",
            name="Y"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=z_values,
            mode="lines",
            name="Z"
        )
    )

    fig.update_layout(
        title=(
            "Accelerometer Segment: "
            + latest_saved_name
        ),
        xaxis_title="Time",
        yaxis_title="Acceleration",
        hovermode="x unified",
        yaxis=dict(
            range=[-1.5, 1.5]
        )
    )

    status = (
        f"Latest saved segment: "
        f"{latest_saved_name} | "
        f"{len(latest_segment)} samples"
    )

    return (
        fig,
        latest_image_src,
        status
    )


if __name__ == "__main__":

    cloud_thread = threading.Thread(
        target=start_arduino_cloud,
        daemon=True
    )

    cloud_thread.start()

    capture_thread = threading.Thread(
        target=segment_capture_worker,
        daemon=True
    )

    capture_thread.start()

    print("Starting Dash...")
    print("Open http://127.0.0.1:8050")

    app.run(
        host="127.0.0.1",
        port=8050,
        debug=False
    )