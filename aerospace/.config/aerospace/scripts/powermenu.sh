#!/bin/bash

# This AppleScript shows a list of choices with a prompt.
# It's wrapped in a "try" block to gracefully handle cancellation.
# If the user presses 'Escape' or the "Cancel" button, the script exits without an error.

osascript -e '
try
    -- Define the list of actions
    set systemActions to {"Log Out", "Power Off", "Restart"}

    tell application "System Events"
        -- Bring the dialog to the front
        activate

        -- Display the list for the user to choose from
        set choiceResult to choose from list systemActions ¬
            with title "Power Mneu" ¬
            with prompt "What would you like to do?" ¬
            default items {"Power Off"} ¬
            OK button name "Confirm" ¬
            cancel button name "Cancel"

        -- If the user clicks "Confirm", the result is a list (e.g., {"Power Off"}).
        -- We get the first item from that list.
        set userChoice to item 1 of choiceResult
    end tell

    -- Execute the correct command based on the choice
    if userChoice is "Power Off" then
        tell application "System Events" to shut down
    else if userChoice is "Restart" then
        tell application "System Events" to restart
    else if userChoice is "Log Out" then
        -- The command to log out is handled by the "loginwindow" process
        tell application "loginwindow" to «event aevtrlgo»
    end if

on error number -128
    -- This part of the script runs if the user presses the Escape key
    -- or the "Cancel" button.
    -- We do nothing here, which simply closes the dialog.
    return
end try
'
