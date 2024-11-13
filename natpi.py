import os
import json
import base64

import io

import simplekml
import numpy as np

from PIL import Image

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.edge.service import Service


class NautilusPilot:
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

    JSON_PATH = "data.json"

    KML_PATH = "data.kml"

    @staticmethod
    def update_kml():
        with open(NautilusPilot.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        kml = simplekml.Kml()

        # points
        for point in json_data["points"]:
            kml.newpoint(
                name=point["name"],
                coords=[(point["longitude"], point["latitude"])],
            )

        # routes
        line = kml.newlinestring(
            coords=[
                (point["longitude"], point["latitude"])
                for point in json_data["route_points"]
            ],
        )

        line.style.linestyle.color = "FFFEE7A6"
        line.style.linestyle.width = 4

        kml.save(NautilusPilot.KML_PATH)

    @staticmethod
    def add_point(name, latitude, longitude, add_to_route):
        with open(NautilusPilot.JSON_PATH, "r") as json_file:
            json_data = json.load(json_file)

        point = {"name": name, "latitude": latitude, "longitude": longitude}

        json_data["points"].append(point)
        if add_to_route:
            json_data["route_points"].append(point)

        with open(NautilusPilot.JSON_PATH, "w") as json_file:
            json.dump(json_data, json_file)

    def __init__(self):
        self.driver = None
        self.canvas = None

    def find_sidebar_button(self):
        pixel_tolerance = 5
        default_gray = np.array([70, 71, 68])

        image_data = self.driver.get_screenshot_as_png()
        image = Image.open(io.BytesIO(image_data))
        image = np.array(image)

        height, width, _ = image.shape
        canvas_height, canvas_width = (
            self.canvas.size["height"],
            self.canvas.size["width"],
        )

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

    def update_kml(self):
        NautilusPilot.update_kml()

        with open(NautilusPilot.KML_PATH, mode="r") as file:
            content = file.read()
            b64_content = base64.b64encode(content.encode()).decode()

        col_offset, row_offset, is_open = self.find_sidebar_button()

        if not is_open:
            # Open the sidebar
            ActionChains(self.driver).move_to_element_with_offset(
                self.canvas, col_offset, row_offset
            ).click().perform()

        self.driver.execute_script(
            NautilusPilot.JS_DRAG_AND_DROP.format(
                b64_content, os.path.basename(NautilusPilot.KML_PATH)
            ),
            self.canvas,
        )

        if not is_open:
            col_offset, row_offset, is_open = self.find_sidebar_button()

        # Close the sidebar
        ActionChains(self.driver).move_to_element_with_offset(
            self.canvas, col_offset, row_offset
        ).click().perform()

    def start_browser(self):
        local_user_data_folder = os.path.join(os.getcwd(), "Local")
        if not os.path.exists(local_user_data_folder):
            os.makedirs(local_user_data_folder)

        options = webdriver.EdgeOptions()
        options.add_argument(f"user-data-dir={local_user_data_folder}")
        options.add_argument("--disable-infobars")

        service = Service("msedgedriver.exe")

        self.driver = webdriver.Edge(service=service, options=options)
        self.driver.get("https://earth.google.com/web")

        WebDriverWait(self.driver, 30).until(
            lambda driver: driver.current_url.find("@") != -1
        )

        self.canvas = self.driver.find_element(By.ID, "earth-canvas")
        self.canvas.click()

    def stop_browser(self):
        self.driver.quit()
        self.driver = None
        self.canvas = None
