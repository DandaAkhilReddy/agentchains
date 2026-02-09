import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import hi from "../locales/hi.json";
import te from "../locales/te.json";
import es from "../locales/es.json";

// Permanently filter i18next's promotional "locize" console.log.
// The message fires in an unpredictable microtask during async init,
// so a temporary override can't reliably catch it. The filter is
// one cheap string check per console.log call — zero practical impact.
const _origLog = console.log;
console.log = (...args: unknown[]) => {
  if (typeof args[0] === "string" && args[0].includes("locize")) return;
  _origLog.apply(console, args);
};

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    te: { translation: te },
    es: { translation: es },
  },
  lng: localStorage.getItem("language") || "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
