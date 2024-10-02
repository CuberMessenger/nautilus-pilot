import os
import io
import cv2
import time
import base64
import argparse
import numpy as np

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


def update_kml(driver, canvas, file_path):
    with open(file_path, mode="r") as file:
        content = file.read()
        b64_content = base64.b64encode(content.encode()).decode()

    col_offset, row_offset, is_open = find_sidebar_button(driver, canvas)

    if not is_open:
        # Open the sidebar
        ActionChains(driver).move_to_element_with_offset(
            canvas, col_offset, row_offset
        ).click().perform()

    driver.execute_script(
        JS_DRAG_AND_DROP.format(b64_content, os.path.basename(file_path)), canvas
    )

    if not is_open:
        col_offset, row_offset, is_open = find_sidebar_button(driver, canvas)

    # Close the sidebar
    ActionChains(driver).move_to_element_with_offset(
        canvas, col_offset, row_offset
    ).click().perform()


def main():
    # default_data_folder = os.path.join(
    #     os.getenv("LOCALAPPDATA"), "Microsoft", "Edge", "User Data", "Default"
    # )
    # options = webdriver.EdgeOptions()
    # options.add_argument(f"user-data-dir={default_data_folder}")

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
    canvas.click()
    # Open the grid view
    # ActionChains(driver).key_down(Keys.CONTROL).send_keys("g").key_up(
    #     Keys.CONTROL
    # ).perform()

    # Load the KML file
    file_path = r"C:\Users\cuber\Desktop\TestKML.kml"
    update_kml(driver, canvas, file_path)

    # pause
    input("Press Enter to continue...")
    driver.quit()


if __name__ == "__main__":
    main()
