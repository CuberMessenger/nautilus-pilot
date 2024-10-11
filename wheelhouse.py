import time
import blessed
import threading


class Wheelhouse:
    def __init__(self):
        self.terminal = blessed.Terminal()

        self.is_online = False
        self.options = [
            "Switch",
            "Add pin",
            "Add way point",
            "Remove the last way point",
            "Leave",
        ]
        self.num_options = len(self.options)
        self.selected_option = 0

        self.measure_terminal()

        self.running_flag = True
        self.listen_flag = True
        self.resize_thread = threading.Thread(target=self.resize_listener)

    def resize_listener(self):
        while True:
            time.sleep(0.1)
            if self.terminal.width != self.width or self.terminal.height != self.height:
                self.measure_terminal()
                self.draw_all()
            if not self.listen_flag:
                break

    def measure_terminal(self):
        self.width = self.terminal.width
        self.height = self.terminal.height

        self.chamber_width = int(self.width * 0.8)
        self.chamber_height = int(self.height * 0.8)

        self.chamber_start_x = (self.width - self.chamber_width) // 2
        self.chamber_start_y = (self.height - self.chamber_height) // 2
        self.chamber_end_x = self.chamber_start_x + self.chamber_width
        self.chamber_end_y = self.chamber_start_y + self.chamber_height

        self.status_x = self.width // 2 - 10
        self.status_y = self.chamber_start_y + 2

        self.options_x = self.width // 2 - 10
        self.options_y = self.status_y + 2

    def draw_chamber(self, title):
        horizontal_line = "-" * (self.chamber_width - 2)

        title = f"-- {title} --"
        start_title_pos = (self.chamber_width - len(title)) // 2
        top_border = f"+{horizontal_line[:start_title_pos]}{title}{horizontal_line[start_title_pos + len(title):]}+"

        bottom_border = "+" + "-" * (self.chamber_width - 2) + "+"

        print(
            self.terminal.move_xy(self.chamber_start_x, self.chamber_start_y)
            + top_border
        )

        for i in range(1, self.chamber_height):
            print(
                self.terminal.move_xy(self.chamber_start_x, self.chamber_start_y + i)
                + f"|{' ' * (self.chamber_width - 2)}|"
            )

        print(
            self.terminal.move_xy(self.chamber_start_x, self.chamber_end_y)
            + bottom_border
        )

    def draw_status(self):
        if self.is_online:
            status_line = f"Status: {self.terminal.green}Online {self.terminal.normal}"
        else:
            status_line = f"Status: {self.terminal.red}Offline{self.terminal.normal}"
        print(self.terminal.move_xy(self.status_x, self.status_y) + status_line)

    def draw_options(self):
        for i, option in enumerate(self.options):
            if i == self.selected_option:
                print(
                    self.terminal.move_xy(self.options_x, self.options_y + i)
                    + f"{self.terminal.reverse}⭐ {option}{self.terminal.normal}"
                )
            else:
                print(
                    self.terminal.move_xy(self.options_x, self.options_y + i)
                    + f"⭐ {option}"
                )

    def draw_all(self):
        print(self.terminal.home + self.terminal.clear)
        self.draw_chamber("Nautilus Wheelhouse")
        self.draw_status()
        self.draw_options()

    def handle_input(self):
        match self.selected_option:
            case 0:  # Switch
                self.is_online = not self.is_online
                self.draw_status()
            case 1:  # Add pin
                pass
            case 2:  # Add way point
                pass
            case 3:  # Remove the last way point
                pass
            case 4:  # Leave
                self.running_flag = False
            case _:
                raise ValueError("Invalid option")

    def start(self):
        try:
            self.resize_thread.start()

            with (
                self.terminal.fullscreen(),
                self.terminal.cbreak(),
                self.terminal.hidden_cursor(),
            ):
                self.draw_all()
                while self.running_flag:
                    key = self.terminal.inkey()
                    if key.code == self.terminal.KEY_ENTER:
                        self.handle_input()
                    elif key.code == self.terminal.KEY_DOWN:
                        self.selected_option = min(
                            self.selected_option + 1, self.num_options - 1
                        )
                        self.draw_options()
                    elif key.code == self.terminal.KEY_UP:
                        self.selected_option = max(self.selected_option - 1, 0)
                        self.draw_options()
        except KeyboardInterrupt:
            pass
        finally:
            self.listen_flag = False
            self.resize_thread.join()


if __name__ == "__main__":
    wheelhouse = Wheelhouse()
    wheelhouse.start()
