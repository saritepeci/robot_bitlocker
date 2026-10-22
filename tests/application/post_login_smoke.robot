*** Settings ***
Documentation       Post-login application smoke tests (start from State E).
...
...                 This suite is the template for the ~800 real application tests. Note
...                 what is NOT here: there is no power-on, no BitLocker handling, no
...                 sign-in code. Each test simply declares "I need a ready desktop" and
...                 begins its actual work. The FIRST test pays for the navigation; every
...                 subsequent test that also needs State E gets it for free (the engine
...                 runs zero transitions because the machine is already there).
Resource            ../../resources/common/settings.resource
Test Setup          Given A Freshly Logged In Desktop Session
Test Tags           application    smoke


*** Test Cases ***
Desktop Is Interactive After Sign In
    [Documentation]    Confirms the precondition delivered a usable desktop (State E).
    Desktop Should Be Ready

A Representative Application Test Begins On The Desktop
    [Documentation]    Stand-in for a real application test. Everything above the
    ...                "ARRANGE" line was handled by the reusable precondition; the
    ...                test body is free to focus purely on application behavior.
    # ARRANGE — the desktop is already ready; launch/attach to the app under test here.
    Desktop Should Be Ready
    # ACT / ASSERT — real application steps would go here, e.g.:
    #   Launch Application    corporate-app
    #   Application Main Window Should Be Visible
    Log    Application test logic starts here, on a fully prepared desktop.    level=INFO
