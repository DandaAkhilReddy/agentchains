/// <reference types="vitest/globals" />
import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { User } from "firebase/auth";

// Mock modules before importing the api instance
vi.mock("../lib/firebase", () => ({
  auth: {
    currentUser: null,
  },
}));

vi.mock("../store/toastStore", () => ({
  useToastStore: {
    getState: vi.fn(() => ({
      addToast: vi.fn(),
    })),
  },
}));

// Import after mocking
import api from "../lib/api";
import { auth } from "../lib/firebase";
import { useToastStore } from "../store/toastStore";

// ---------------------------------------------------------------------------
// Test Helpers
// ---------------------------------------------------------------------------

/**
 * Extract the request interceptor function from the api instance
 */
const getRequestInterceptor = () => {
  // @ts-expect-error - accessing private interceptors for testing
  const handlers = api.interceptors.request.handlers;
  return handlers[0]?.fulfilled;
};

/**
 * Extract the response error interceptor function from the api instance
 */
const getResponseErrorInterceptor = () => {
  // @ts-expect-error - accessing private interceptors for testing
  const handlers = api.interceptors.response.handlers;
  return handlers[0]?.rejected;
};

/**
 * Create a mock Axios request config
 */
const createMockConfig = (): InternalAxiosRequestConfig => ({
  headers: {} as any,
  method: "GET",
  url: "/test",
});

/**
 * Create a mock Axios error with response
 */
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

/**
 * Create a mock Axios error without response (network error)
 */
const createNetworkError = (): AxiosError => {
  const error = new Error("Network Error") as AxiosError;
  error.isAxiosError = true;
  error.config = createMockConfig();
  return error;
};

// ---------------------------------------------------------------------------
// Reset state before each test
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.clearAllMocks();
  // Reset auth.currentUser
  (auth as any).currentUser = null;
  // Reset window.location.href
  delete (window as any).location;
  window.location = { href: "" } as any;
});

// ---------------------------------------------------------------------------
// Axios Instance Configuration Tests
// ---------------------------------------------------------------------------
describe("api axios instance configuration", () => {
  it("has correct baseURL from env or empty string", () => {
    // baseURL is set from VITE_API_BASE_URL or defaults to ""
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

// ---------------------------------------------------------------------------
// Request Interceptor Tests
// ---------------------------------------------------------------------------
describe("request interceptor", () => {
  it("attaches Bearer token when user exists and getIdToken succeeds", async () => {
    const mockToken = "mock-firebase-token-123";
    const mockUser = {
      uid: "user123",
      getIdToken: vi.fn().mockResolvedValue(mockToken),
    } as unknown as User;

    (auth as any).currentUser = mockUser;

    const requestInterceptor = getRequestInterceptor();
    const config = createMockConfig();

    const result = await requestInterceptor(config);

    expect(mockUser.getIdToken).toHaveBeenCalledTimes(1);
    expect(result.headers.Authorization).toBe(`Bearer ${mockToken}`);
  });

  it("does not attach token when user is null", async () => {
    (auth as any).currentUser = null;

    const requestInterceptor = getRequestInterceptor();
    const config = createMockConfig();

    const result = await requestInterceptor(config);

    expect(result.headers.Authorization).toBeUndefined();
  });

  it("does not attach token when user is undefined", async () => {
    (auth as any).currentUser = undefined;

    const requestInterceptor = getRequestInterceptor();
    const config = createMockConfig();

    const result = await requestInterceptor(config);

    expect(result.headers.Authorization).toBeUndefined();
  });

  it("handles getIdToken failure gracefully without throwing", async () => {
    const mockUser = {
      uid: "user123",
      getIdToken: vi.fn().mockRejectedValue(new Error("Token refresh failed")),
    } as unknown as User;

    (auth as any).currentUser = mockUser;

    const requestInterceptor = getRequestInterceptor();
    const config = createMockConfig();

    // Should not throw, should return config without token
    await expect(requestInterceptor(config)).resolves.toBeDefined();
    const result = await requestInterceptor(config);

    expect(mockUser.getIdToken).toHaveBeenCalledTimes(2); // called twice due to previous expect
    expect(result.headers.Authorization).toBeUndefined();
  });

  it("returns the config object for successful token attachment", async () => {
    const mockToken = "another-token";
    const mockUser = {
      uid: "user456",
      getIdToken: vi.fn().mockResolvedValue(mockToken),
    } as unknown as User;

    (auth as any).currentUser = mockUser;

    const requestInterceptor = getRequestInterceptor();
    const config = createMockConfig();

    const result = await requestInterceptor(config);

    expect(result).toBe(config); // Same object reference
    expect(result.headers).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Response Interceptor Tests - Success
// ---------------------------------------------------------------------------
describe("response interceptor - success", () => {
  it("passes through successful responses unchanged", () => {
    // The success handler in the interceptor is just: (response) => response
    // We can verify this by checking that axios responses work normally
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

// ---------------------------------------------------------------------------
// Response Interceptor Tests - Error Handling
// ---------------------------------------------------------------------------
describe("response interceptor - error handling", () => {
  let mockAddToast: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockAddToast = vi.fn();
    (useToastStore.getState as ReturnType<typeof vi.fn>).mockReturnValue({
      addToast: mockAddToast,
    });
  });

  it("redirects to /login on 401 error", async () => {
    const error = createMockError(401);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(window.location.href).toBe("/login");
    expect(mockAddToast).not.toHaveBeenCalled(); // No toast for 401
  });

  it("shows warning toast on 429 error (rate limit)", async () => {
    const error = createMockError(429);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "warning",
      message: "Too many requests. Please wait a moment.",
    });
    expect(window.location.href).toBe(""); // No redirect
  });

  it("shows error toast on 500 server error", async () => {
    const error = createMockError(500);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).toHaveBeenCalledWith({
      type: "error",
      message: "Server error. Please try again later.",
    });
    expect(window.location.href).toBe(""); // No redirect
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
    expect(window.location.href).toBe(""); // No redirect
  });

  it("does not show toast for 400 bad request", async () => {
    const error = createMockError(400);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).not.toHaveBeenCalled();
    expect(window.location.href).toBe(""); // No redirect
  });

  it("does not show toast for 404 not found", async () => {
    const error = createMockError(404);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).not.toHaveBeenCalled();
    expect(window.location.href).toBe(""); // No redirect
  });

  it("does not show toast for 403 forbidden", async () => {
    const error = createMockError(403);
    const errorInterceptor = getResponseErrorInterceptor();

    await expect(errorInterceptor(error)).rejects.toEqual(error);

    expect(mockAddToast).not.toHaveBeenCalled();
    expect(window.location.href).toBe(""); // No redirect
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

// ---------------------------------------------------------------------------
// Integration Tests - Full Request/Response Cycle
// ---------------------------------------------------------------------------
describe("api integration", () => {
  it("can be imported and used as axios instance", () => {
    expect(api).toBeDefined();
    expect(api.get).toBeDefined();
    expect(api.post).toBeDefined();
    expect(api.put).toBeDefined();
    expect(api.delete).toBeDefined();
    expect(api.interceptors).toBeDefined();
  });

  it("has both request and response interceptors registered", () => {
    // @ts-expect-error - accessing private interceptors for testing
    const requestHandlers = api.interceptors.request.handlers;
    // @ts-expect-error - accessing private interceptors for testing
    const responseHandlers = api.interceptors.response.handlers;

    expect(requestHandlers.length).toBeGreaterThan(0);
    expect(responseHandlers.length).toBeGreaterThan(0);
  });
});
