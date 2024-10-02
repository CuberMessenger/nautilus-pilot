import os
import time
import base64
import argparse
import subprocess

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

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


def main():
    driver = webdriver.Edge()
    driver.get("https://earth.google.com/web")

    time.sleep(10)

    # click "ctrl+G"
    ActionChains(driver).key_down(Keys.CONTROL).send_keys("g").key_up(
        Keys.CONTROL
    ).perform()

    time.sleep(1)

    # drop a local file to body
    file_path = r"C:\Users\cuber\Desktop\TestKML.kml"
    canvas = driver.find_element(By.ID, "earth-canvas")

    with open(file_path, mode="r") as file:
        content = file.read()
        b64_content = base64.b64encode(content.encode()).decode()

    driver.execute_script(
        JS_DRAG_AND_DROP.format(b64_content, os.path.basename(file_path)), canvas
    )

    # pause
    input("Press Enter to continue...")
    driver.close()


if __name__ == "__main__":
    main()
