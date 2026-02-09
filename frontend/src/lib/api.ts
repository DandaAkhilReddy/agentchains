import axios from "axios";
import { auth } from "./firebase";
import { useToastStore } from "../store/toastStore";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Auto-attach Firebase token
api.interceptors.request.use(async (config) => {
  const user = auth.currentUser;
  if (user) {
    const token = await user.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors — redirect, toast notifications
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const { addToast } = useToastStore.getState();

    if (error.response) {
      const status = error.response.status;

      if (status === 401) {
        window.location.href = "/login";
      } else if (status === 429) {
        addToast({
          type: "warning",
          message: "Too many requests. Please wait a moment.",
        });
      } else if (status >= 500) {
        addToast({
          type: "error",
          message: "Server error. Please try again later.",
        });
      }
    } else {
      // No response — network error
      addToast({
        type: "error",
        message: "Network error. Check your connection.",
      });
    }

    return Promise.reject(error);
  }
);

export default api;
