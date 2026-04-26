(function () {
    const themes = [
        ["matrix", "Matrix"],
        ["tanuki", "Tanuki Sunset"],
        ["mono", "Black & White"],
        ["ember", "Red Ember"],
        ["nebula", "Blue Nebula"]
    ];
    const storageKey = "uil_theme";

    function applyTheme(theme) {
        const selected = themes.some(([value]) => value === theme) ? theme : "matrix";
        document.body.dataset.theme = selected;
        localStorage.setItem(storageKey, selected);
    }

    function buildPicker() {
        const picker = document.createElement("div");
        picker.className = "theme-picker";

        const label = document.createElement("label");
        label.htmlFor = "theme-select";
        label.textContent = "Theme";

        const select = document.createElement("select");
        select.id = "theme-select";
        for (const [value, text] of themes) {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = text;
            select.appendChild(option);
        }

        const savedTheme = localStorage.getItem(storageKey) || "matrix";
        select.value = savedTheme;
        applyTheme(savedTheme);

        select.addEventListener("change", () => {
            applyTheme(select.value);
        });

        picker.appendChild(label);
        picker.appendChild(select);
        document.body.appendChild(picker);
    }

    document.addEventListener("DOMContentLoaded", buildPicker);
})();
