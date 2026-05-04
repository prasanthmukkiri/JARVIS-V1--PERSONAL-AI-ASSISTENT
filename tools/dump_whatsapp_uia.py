from pywinauto import Application
from pathlib import Path
import traceback


def main():
    out = Path("tools") / "send_debug" / "whatsapp_uia_dump.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        app = None
        # Try connecting by known executable name first
        try:
            app = Application(backend="uia").connect(path="WhatsApp.exe")
        except Exception:
            pass
        # If that failed, try connecting by window title or handle
        if app is None:
            try:
                app = Application(backend="uia").connect(title_re=".*WhatsApp.*")
            except Exception:
                # last resort: try any window handle matching WhatsApp title
                from pywinauto.findwindows import find_windows
                handles = find_windows(title_re=".*WhatsApp.*")
                if handles:
                    app = Application(backend="uia").connect(handle=handles[0])
        if app is None:
            raise RuntimeError("Could not connect to WhatsApp window via path or title")
        win = app.window(title_re=".*WhatsApp.*")
        # print_control_identifiers can write directly to a file
        win.print_control_identifiers(filename=str(out))
        print("Wrote UIA dump to", out)
    except Exception:
        with out.open("w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        print("Failed to write UIA dump — see", out)


if __name__ == '__main__':
    main()
