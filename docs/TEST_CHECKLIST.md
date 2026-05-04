# JARVISS Test Checklist

Use this checklist to test the assistant end to end after changes to planning, execution, wake-word handling, or action modules.

## How to Use

- Run the assistant normally with `python main.py`.
- Speak each command clearly after the wake word.
- Mark each item as `Pass`, `Fail`, or `Needs Review`.
- Re-test any failed item after fixes.

---

## 1. Startup & Voice Pipeline

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Wake word detection | Say the wake word once | Jarvis starts listening | [ ] |
| Follow-up listening | Say a follow-up command after wake word | Jarvis keeps context | [ ] |
| Stop command | Say stop / cancel | Jarvis stops or cancels current action | [ ] |
| No wake word | Speak a random sentence | Jarvis should ignore it | [ ] |
| Low-volume speech | Speak softly | Jarvis still transcribes reasonably | [ ] |

---

## 2. Core Desktop Actions

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Open app | `open chrome` | Chrome opens | [ ] |
| Open calculator | `open calculator` | Calculator opens | [ ] |
| Open notepad | `open notepad` | Notepad opens | [ ] |
| App not installed | `open an app that does not exist` | Graceful failure message | [ ] |
| Window focus | Switch away and ask Jarvis to open an app | Correct app becomes active | [ ] |

---

## 3. Planner Tests

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Direct message plan | `send a message to pk saying hii` | One valid `send_message` step | [ ] |
| Search plan | `search for python tutorials` | One valid `web_search` step | [ ] |
| Open app plan | `open chrome` | One valid `open_app` step | [ ] |
| Weather plan | `what is the weather in london` | One valid `weather_report` step | [ ] |
| Multi-step command | `open chrome and search for python tutorials` | Plan should decompose into steps | [ ] |

---

## 4. Executor & Recovery Tests

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Valid tool execution | Run any supported command | Step executes successfully | [ ] |
| Invalid app name | `open xyznotrealapp` | Retry / failure handling appears | [ ] |
| Bad contact name | `send a message to unknown contact saying hello` | Clean error or no-send behavior | [ ] |
| Replan flow | Ask for a task that fails once | Executor retries or replans | [ ] |
| Cancel flow | Start a long task and cancel it | Task stops cleanly | [ ] |

---

## 5. Web, Weather, and Media

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Web search | `search for ai news today` | Search results returned | [ ] |
| Weather | `what is the weather in mumbai` | Weather summary returned | [ ] |
| YouTube | `play a youtube video about machine learning` | Video opens or search results appear | [ ] |
| Browser navigation | `open github.com` | Browser opens to the site | [ ] |

---

## 6. File & System Utilities

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| List desktop files | `list files on desktop` | Desktop contents shown | [ ] |
| Find files | `find pdf files in documents` | Matching files listed | [ ] |
| Open file | `open file notes.txt` | File opens in default app | [ ] |
| Create reminder file | `save this to a file` | File written successfully | [ ] |

---

## 7. Reminder & Memory

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Set reminder | `remind me in 2 minutes to drink water` | Reminder created | [ ] |
| Show reminders | `show my reminders` | Reminder list shown | [ ] |
| Remember preference | `remember that I like coffee` | Memory saved | [ ] |
| Recall memory | `what do I like` | Jarvis recalls saved preference | [ ] |

---

## 8. Messaging Tests

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| WhatsApp send | `send a message to pk saying hii` | Message sends successfully | [ ] |
| Contact verification | Use a similar contact name | Jarvis picks the correct contact | [ ] |
| Message text accuracy | Send a longer sentence | Text should match exactly | [ ] |
| Failure path | Use an invalid recipient | No incorrect send occurs | [ ] |

---

## 9. Error Handling Tests

| Test | Command / Action | Expected Result | Status |
|------|------------------|-----------------|--------|
| Missing info | `send a message` | Jarvis asks for details | [ ] |
| Unsupported command | Ask something Jarvis cannot do | Clear fallback response | [ ] |
| API failure | Temporarily break an API key | Friendly error and fallback | [ ] |
| Retry handling | Re-run a failed command | Behavior improves or explains failure | [ ] |

---

## 10. Regression Checklist

- [ ] `main.py` starts without errors
- [ ] Wake word detection works
- [ ] Planner returns valid plans
- [ ] Executor runs tool steps
- [ ] Replan/retry behavior works
- [ ] WhatsApp send flow works
- [ ] Web search works
- [ ] Weather works
- [ ] Reminders work
- [ ] Memory recall works
- [ ] Logs are written to `jarvis_log.txt`

---

## Notes

- If a test fails, capture the exact command, the expected result, and the actual result.
- Use `tools/send_debug/` screenshots for UI automation failures.
- Re-run the planner and executor tests after any code change affecting task handling.
