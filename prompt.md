Please help me write a TUI frontend using the python library called Blessed.
Here is the requirements:

1. When the program starts, it displays a rectangle area with a border.
2. The border is formed with single lines.
3. The first row of the rectangle will have a title replacing some border characters. Like "...-- Title --...".
4. The rectangle should roughly take up 80% of the terminal window and centered horizontally and vertically.
5. Make the positioning code rubost to handle different terminal sizes and future changes.

6. Inside the rectangle, there should be some rows of text centered horizontally.
7. The first line is a display line like "Status: Offline", and when a backend boolean variable changes, it will becomes "Status: Online". "Offline" and "Online" should be in red and green respectively.
8. The rest of the lines are options like "[ ] Option 1".
9. At first the first option is selected, and the user can navigate between options using arrow keys.
10. When an option is selected, it should be highlighted with a different background color.
11. The user can press Enter to activate the option.
12. The last option is a "Quit" option, which when activate , the program exits.
13. The rest options will invoke corresponding functions when activated, leave them dummy functions for now.

