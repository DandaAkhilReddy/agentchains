/// <reference types="vitest/globals" />
import { AxiosError, InternalAxiosRequestConfig } from "axios";

// Auth is paused — api.ts has no request interceptor, no 401 redirect

vi.mock("../store/toastStore", () => ({
  useToastStore: {
    getState: vi.fn(() => ({
      addToast: vi.fn(),
    })),
  },
}));

import api from "../lib/api";
import { useToastStore } from "../store/toastStore";

const createMockConfig = (): InternalAxiosRequestConfig => ({
  headers: {} as any,
  method: "GET",
  url: "/test",
});

const createMockError = (status: number): AxiosError => {
  const error = new Error("Request failed") as AxiosError;
  error.isAxiosError = true;
  error.response = {
    status,
    data: {},
    statusText: "Error",
    headers: {},
    config: createMockConfig(),
  };
  error.config = createMockConfig();
  return error;
};

const createNetworkError = (): AxiosError => {
  const error = new Error("Network Error") as AxiosError;
  error.isAxiosError = true;
  error.config = createMockConfig();
  return error;
};

const getResponseErrorInterceptor = () => {
  // @ts-expect-error - accessing private interceptors for testing
  const handlers = api.interceptors.response.handlers;
  return handlers[0]?.rejected;
};

beforeEach(() => {
  vi.clearAllMocks();
  delete (window as any).location;
  window.location = { href: "" } as any;
});

describe("api axios instance configuration", () => {
  it("has correct baseURL from env or empty string", () => {
    expect(api.defaults.baseURL).toBeDefined();
    expect(typeof api.defaults.baseURL).toBe("string");
  });

  it("has timeout set to 30000ms", () => {
    expect(api.defaults.timeout).toBe(30000);
  });

  it("has Content-Type header set to application/json", () => {
    expect(api.defaults.headers["Content-Type"]).toBe("application/json");
  });
});

describe("request interceptor (auth paused)", () => {
  it("has no request interceptor registered", () => {
    // @ts-expect-error - accessing private interceptors for testing
    const requestHandlers = api.interceptors.request.handlers.filter(Boolean);
    expect(requestHandlers.length).toBe(0);
  });
});

describe("response interceptor - success", () => {
  it("passes through successful responses unchanged", () => {
    const mockResponse = {
      data: { message: "success" },
      status: 200,
      statusText: "OK",
      headers: {},
      config: createMockConfig(),
    };

    // @ts-expect-error - accessing private interceptors for testing
    const handlers = api.interceptors.response.handlers;
    const successHandler = handlers[0]?.fulfilled;

    expect(successHandler).toBeDefined();
    const result = successHandler(mockResponse);
    expect(result).toBe(mockResponse);
  });
});

describe("response interceptor - error handling (auth paused)", () => {
  let mockAddToast: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockAddToast = vi.fn();
    (useToastStore.getState as ReturnType<typeof vi.fn>).mockReturnValue({
      addToast: mockAddToast,
    });
  });

  it("does NOT redirect to /login on 401 error", async () => {
    const error = createMockError(401);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(window.location.href).toBe(""); // No redirect
    expect(mockAddToast).not.toHaveBeenCalled();
  });

  it("shows warning toast on 429 error (rate limit)", async () => {
    const error = createMockError(429);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "warning",
      message: "Too many requests. Please wait a moment.",
    });
  });

  it("shows error toast on 500 server error", async () => {
    const error = createMockError(500);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "error",
      message: "Server error. Please try again later.",
    });
  });

  it("shows error toast on 502 bad gateway", async () => {
    const error = createMockError(502);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "error",
      message: "Server error. Please try again later.",
    });
  });

  it("shows error toast on 503 service unavailable", async () => {
    const error = createMockError(503);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "error",
      message: "Server error. Please try again later.",
    });
  });

  it("shows network error toast when no response", async () => {
    const error = createNetworkError();
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "error",
      message: "Network error. Check your connection.",
    });
  });

  it("does not show toast for 400 bad request", async () => {
    const error = createMockError(400);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).not.toHaveBeenCalled();
  });

  it("does not show toast for 404 not found", async () => {
    const error = createMockError(404);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).not.toHaveBeenCalled();
  });

  it("does not show toast for 403 forbidden", async () => {
    const error = createMockError(403);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).not.toHaveBeenCalled();
  });

  it("always rejects with the original error", async () => {
    const error429 = createMockError(429);
    const error500 = createMockError(500);
    const networkError = createNetworkError();

    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error429)).rejects.toEqual(error429);
    await expect(errorInterceptor(error500)).rejects.toEqual(error500);
    await expect(errorInterceptor(networkError)).rejects.toEqual(networkError);
  });
});

describe("api integration", () => {
  it("can be imported and used as axios instance", () => {
    expect(api).toBeDefined();
    expect(api.get).toBeDefined();
    expect(api.post).toBeDefined();
    expect(api.put).toBeDefined();
    expect(api.delete).toBeDefined();
    expect(api.interceptors).toBeDefined();
  });

  it("has only response interceptor registered (no request interceptor)", () => {
    // @ts-expect-error - accessing private interceptors for testing
    const responseHandlers = api.interceptors.response.handlers.filter(Boolean);
    expect(responseHandlers.length).toBeGreaterThan(0);
  });
});
