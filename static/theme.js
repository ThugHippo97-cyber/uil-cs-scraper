(function () {
    const storageKey = "uil_theme";
    const darkValue = "dark";

    function applyTheme(theme) {
        if (theme === darkValue) {
            document.body.dataset.theme = darkValue;
        } else {
            delete document.body.dataset.theme;
        }
    }

    function savedTheme() {
        return localStorage.getItem(storageKey) === darkValue ? darkValue : "light";
    }

    function setSavedTheme(theme) {
        if (theme === darkValue) {
            localStorage.setItem(storageKey, darkValue);
        } else {
            localStorage.removeItem(storageKey);
        }
    }

    function labelFor(theme) {
        return theme === darkValue ? "Dark" : "Light";
    }

    function buildToggle() {
        const navTarget = document.querySelector(".nav-actions") || document.querySelector(".top-nav");
        if (!navTarget || document.querySelector(".theme-toggle")) return;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "theme-toggle";

        const text = document.createElement("span");
        text.className = "theme-toggle-label";

        const track = document.createElement("span");
        track.className = "theme-toggle-track";
        track.setAttribute("aria-hidden", "true");

        button.appendChild(text);
        button.appendChild(track);

        function sync(theme) {
            const isDark = theme === darkValue;
            button.setAttribute("aria-pressed", String(isDark));
            button.setAttribute("aria-label", `Switch to ${isDark ? "light" : "dark"} mode`);
            text.textContent = labelFor(theme);
        }

        let current = savedTheme();
        applyTheme(current);
        sync(current);

        button.addEventListener("click", () => {
            current = current === darkValue ? "light" : darkValue;
            applyTheme(current);
            setSavedTheme(current);
            sync(current);
        });

        navTarget.insertBefore(button, navTarget.firstChild);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", buildToggle);
    } else {
        buildToggle();
    }
})();
