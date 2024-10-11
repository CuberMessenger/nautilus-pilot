import os
import io
import cv2
import time
import json
import base64
import argparse
import simplekml
import numpy as np

from blessed import Terminal

from PIL import Image

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.edge.service import Service

JS_DRAG_AND_DROP = """
    var b64File = '{}';
    var filename = '{}';
    var contentType = 'text/plain';

    var binary = atob(b64File);
    var array = [];
    for (var i = 0; i < binary.length; i++) {{
        array.push(binary.charCodeAt(i));
    }}
    var uint8Array = new Uint8Array(array);

    var file = new File([uint8Array], filename, {{type: contentType}});

    var dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);

    var canvas = arguments[0];

    ['dragenter', 'dragover', 'drop'].forEach(function(eventName) {{
        var event = new DragEvent(eventName, {{
            dataTransfer: dataTransfer,
            bubbles: true,
            cancelable: true
        }});
        canvas.dispatchEvent(event);
    }});
"""


def find_sidebar_button(driver, canvas):
    pixel_tolerance = 5
    default_gray = np.array([70, 71, 68])

    image_data = driver.get_screenshot_as_png()
    image = Image.open(io.BytesIO(image_data))
    image = np.array(image)

    height, width, _ = image.shape
    canvas_height, canvas_width = canvas.size["height"], canvas.size["width"]

    top_bar_height = 72
    # top_bar_height = 0
    # while (image[top_bar_height, -1] == 255).all():
    #     top_bar_height += 1

    # image = image[top_bar_height:, :, :]

    col = 0
    row = int(round((height - top_bar_height) / 2 + top_bar_height))
    for try_col in range(width // 2):
        if np.sum(np.abs(image[row, try_col] - default_gray)) < pixel_tolerance:
            col = try_col
            break

    if col == 0:
        raise Exception("Could not find the sidebar button!")

    is_open = col > top_bar_height

    col = int(round(col * canvas_width / width))
    row = int(round(row * canvas_height / height))

    col_offset = col - canvas_width // 2
    row_offset = row - canvas_height // 2
    return col_offset, row_offset, is_open


def json_to_kml(json_path, kml_path):
    with open(json_path, "r") as json_file:
        json_data = json.load(json_file)

    kml = simplekml.Kml()

    # points
    for point in json_data["points"]:
        kml.newpoint(
            name=point["name"],
            description=point["description"],
            coords=[(point["longitude"], point["latitude"])],
        )

    # routes
    for route in json_data["routes"]:
        line = kml.newlinestring(
            name=route["name"],
            description=route["description"],
            coords=[
                (point["longitude"], point["latitude"]) for point in route["points"]
            ],
        )

        line.style.linestyle.color = "FFFEE7A6"
        line.style.linestyle.width = 4

    kml.save(kml_path)


def update_kml(driver, canvas, json_path):
    kml_path = json_path.replace(".json", ".kml")
    json_to_kml(json_path, kml_path)

    with open(kml_path, mode="r") as file:
        content = file.read()
        b64_content = base64.b64encode(content.encode()).decode()

    col_offset, row_offset, is_open = find_sidebar_button(driver, canvas)

    if not is_open:
        # Open the sidebar
        ActionChains(driver).move_to_element_with_offset(
            canvas, col_offset, row_offset
        ).click().perform()

    driver.execute_script(
        JS_DRAG_AND_DROP.format(b64_content, os.path.basename(kml_path)), canvas
    )

    if not is_open:
        col_offset, row_offset, is_open = find_sidebar_button(driver, canvas)

    # Close the sidebar
    ActionChains(driver).move_to_element_with_offset(
        canvas, col_offset, row_offset
    ).click().perform()


def start_browser():
    local_user_data_folder = os.path.join(os.getcwd(), "Local")
    if not os.path.exists(local_user_data_folder):
        os.makedirs(local_user_data_folder)

    options = webdriver.EdgeOptions()
    options.add_argument(f"user-data-dir={local_user_data_folder}")
    options.add_argument("--disable-infobars")

    service = Service("msedgedriver.exe")

    driver = webdriver.Edge(service=service, options=options)
    driver.get("https://earth.google.com/web")

    WebDriverWait(driver, 30).until(lambda driver: driver.current_url.find("@") != -1)

    canvas = driver.find_element(By.ID, "earth-canvas")
    canvas.click().perform()

    return driver, canvas


def main():
    driver, canvas = start_browser()

    json_path = r"data-template.json"
    update_kml(driver, canvas, json_path)

    # pause
    input("Press Enter to continue...")
    driver.quit()


def tui_demo():
    terminal = Terminal()

    print(terminal.home + terminal.clear)
    print(terminal.move_x(terminal.width // 2 - 1))
    print(terminal.move_y(terminal.height // 2 - 1))




if __name__ == "__main__":
    tui_demo()
