import sys
import traceback
import os
import threading
import queue
from datetime import datetime

from arduino_iot_cloud import ArduinoCloudClient

from dash import Dash, dcc, html, Input, Output, no_update
import plotly.graph_objects as go


DEVICE_ID = "4e207963-8877-4378-bfb1-04c7d078ad82"
SECRET_KEY = "DuSEgXjKbJIBX@78muu#tkUCm"

data_queue = queue.Queue()

latest_x = None
latest_y = None
latest_z = None

new_x = False
new_y = False
new_z = False


def process_combined_data():
    global latest_x, latest_y, latest_z
    global new_x, new_y, new_z

    if new_x and new_y and new_z:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        data_queue.put({
            "time": timestamp,
            "x": latest_x,
            "y": latest_y,
            "z": latest_z
        })

        print(
            f"Queued: {timestamp}, "
            f"X={latest_x}, "
            f"Y={latest_y}, "
            f"Z={latest_z}"
        )

        new_x = False
        new_y = False
        new_z = False


def on_accelerometer_x_changed(client, value):
    global latest_x, new_x

    latest_x = value
    new_x = True

    print(f"New accelerometer X: {value}")
    process_combined_data()


def on_accelerometer_y_changed(client, value):
    global latest_y, new_y

    latest_y = value
    new_y = True

    print(f"New accelerometer Y: {value}")
    process_combined_data()


def on_accelerometer_z_changed(client, value):
    global latest_z, new_z

    latest_z = value
    new_z = True

    print(f"New accelerometer Z: {value}")
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



def register_smooth_stream(
        app,
        graph_id,
        interval_id,
        source_queue,
        sampling_interval=100,
        max_points=200
):

    @app.callback(
        Output(graph_id, "extendData"),
        Input(interval_id, "n_intervals")
    )
    def update_graph(n):

        samples = []
        while not source_queue.empty():

            try:
                samples.append(
                    source_queue.get_nowait()
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

            max_points
        )


app = Dash(__name__)


figure = go.Figure()


figure.add_trace(
    go.Scatter(
        x=[],
        y=[],
        mode="lines",
        name="Accelerometer X"
    )
)


figure.add_trace(
    go.Scatter(
        x=[],
        y=[],
        mode="lines",
        name="Accelerometer Y"
    )
)


figure.add_trace(
    go.Scatter(
        x=[],
        y=[],
        mode="lines",
        name="Accelerometer Z"
    )
)


figure.update_layout(
    title="Live Smartphone Accelerometer Data",
    xaxis_title="Time",
    yaxis_title="Acceleration",
    hovermode="x unified",
    yaxis=dict(
        range=[-1.5, 1.5]
    )
)

figure.update_xaxes(
    nticks=10
)


app.layout = html.Div([

    html.H1(
        "Smartphone Accelerometer Live Monitor",
        style={"textAlign": "center"}
    ),

    html.P(
        "Real-time accelerometer X, Y and Z data",
        style={"textAlign": "center"}
    ),

    dcc.Graph(
        id="live-accelerometer-graph",
        figure=figure
    ),

    dcc.Interval(
        id="graph-update",
        interval=100,
        n_intervals=0
    )

])


register_smooth_stream(
    app=app,
    graph_id="live-accelerometer-graph",
    interval_id="graph-update",
    source_queue=data_queue,
    max_points=200
)


if __name__ == "__main__":

    cloud_thread = threading.Thread(
        target=start_arduino_cloud,
        daemon=True
    )

    cloud_thread.start()

    print("Starting Dash...")
    print("Open http://127.0.0.1:8050")

    app.run(
        host="127.0.0.1",
        port=8050,
        debug=False
    )