import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "../locales/en.json";
import hi from "../locales/hi.json";
import te from "../locales/te.json";
import es from "../locales/es.json";

// Suppress i18next promotional console.log during init
const _origLog = console.log;
console.log = (...args: unknown[]) => {
  if (typeof args[0] === "string" && args[0].includes("locize")) return;
  _origLog(...args);
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
}).then(() => {
  console.log = _origLog;
});

export default i18n;
