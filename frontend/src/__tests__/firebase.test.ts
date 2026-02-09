/// <reference types="vitest/globals" />

// Mock firebase modules before importing the config
vi.mock("firebase/app", () => ({
  initializeApp: vi.fn(() => ({ name: "test-app" })),
}));

vi.mock("firebase/auth", () => ({
  getAuth: vi.fn(() => ({ currentUser: null, signOut: vi.fn() })),
  GoogleAuthProvider: vi.fn(),
  signInWithPopup: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  updateProfile: vi.fn(),
  onAuthStateChanged: vi.fn(),
}));

describe("Firebase Configuration", () => {
  beforeEach(() => {
    import.meta.env.VITE_FIREBASE_API_KEY = "test-api-key";
    import.meta.env.VITE_FIREBASE_AUTH_DOMAIN = "test-auth-domain";
    import.meta.env.VITE_FIREBASE_PROJECT_ID = "test-project-id";
    import.meta.env.VITE_FIREBASE_STORAGE_BUCKET = "test-storage-bucket";
    import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID = "test-sender-id";
    import.meta.env.VITE_FIREBASE_APP_ID = "test-app-id";
  });

  it("should call initializeApp with config from env vars", async () => {
    const { initializeApp } = await import("firebase/app");
    await import("../lib/firebase");
    // initializeApp was called at module init — check it was called at least once
    expect(initializeApp).toHaveBeenCalled();
  });

  it("should export auth instance", async () => {
    const { auth } = await import("../lib/firebase");
    expect(auth).toBeDefined();
    expect(auth).toHaveProperty("currentUser");
  });

  it("should export googleProvider instance", async () => {
    const { googleProvider } = await import("../lib/firebase");
    expect(googleProvider).toBeDefined();
  });

  it("should re-export signInWithPopup", async () => {
    const firebaseAuthModule = await import("firebase/auth");
    const firebaseModule = await import("../lib/firebase");
    expect(firebaseModule.signInWithPopup).toBe(firebaseAuthModule.signInWithPopup);
  });

  it("should re-export createUserWithEmailAndPassword", async () => {
    const firebaseAuthModule = await import("firebase/auth");
    const firebaseModule = await import("../lib/firebase");
    expect(firebaseModule.createUserWithEmailAndPassword).toBe(
      firebaseAuthModule.createUserWithEmailAndPassword
    );
  });

  it("should re-export signInWithEmailAndPassword", async () => {
    const firebaseAuthModule = await import("firebase/auth");
    const firebaseModule = await import("../lib/firebase");
    expect(firebaseModule.signInWithEmailAndPassword).toBe(
      firebaseAuthModule.signInWithEmailAndPassword
    );
  });

  it("should re-export sendPasswordResetEmail", async () => {
    const firebaseAuthModule = await import("firebase/auth");
    const firebaseModule = await import("../lib/firebase");
    expect(firebaseModule.sendPasswordResetEmail).toBe(
      firebaseAuthModule.sendPasswordResetEmail
    );
  });

  it("should re-export updateProfile", async () => {
    const firebaseAuthModule = await import("firebase/auth");
    const firebaseModule = await import("../lib/firebase");
    expect(firebaseModule.updateProfile).toBe(firebaseAuthModule.updateProfile);
  });

  describe("Configuration Validation", () => {
    let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
      vi.resetModules();
    });

    afterEach(() => {
      consoleErrorSpy.mockRestore();
      vi.resetModules();
    });

    it("should log error when apiKey is missing", async () => {
      import.meta.env.VITE_FIREBASE_API_KEY = "";
      import.meta.env.VITE_FIREBASE_AUTH_DOMAIN = "test-auth-domain";
      import.meta.env.VITE_FIREBASE_PROJECT_ID = "test-project-id";
      await import("../lib/firebase");
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Firebase config missing: apiKey. Check VITE_FIREBASE_* env vars."
      );
    });

    it("should log error when authDomain is missing", async () => {
      import.meta.env.VITE_FIREBASE_API_KEY = "test-api-key";
      import.meta.env.VITE_FIREBASE_AUTH_DOMAIN = "";
      import.meta.env.VITE_FIREBASE_PROJECT_ID = "test-project-id";
      await import("../lib/firebase");
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Firebase config missing: authDomain. Check VITE_FIREBASE_* env vars."
      );
    });

    it("should log error when projectId is missing", async () => {
      import.meta.env.VITE_FIREBASE_API_KEY = "test-api-key";
      import.meta.env.VITE_FIREBASE_AUTH_DOMAIN = "test-auth-domain";
      import.meta.env.VITE_FIREBASE_PROJECT_ID = "";
      await import("../lib/firebase");
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Firebase config missing: projectId. Check VITE_FIREBASE_* env vars."
      );
    });

    it("should log multiple errors when multiple required keys are missing", async () => {
      import.meta.env.VITE_FIREBASE_API_KEY = "";
      import.meta.env.VITE_FIREBASE_AUTH_DOMAIN = "";
      import.meta.env.VITE_FIREBASE_PROJECT_ID = "test-project-id";
      await import("../lib/firebase");
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Firebase config missing: apiKey. Check VITE_FIREBASE_* env vars."
      );
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Firebase config missing: authDomain. Check VITE_FIREBASE_* env vars."
      );
      expect(consoleErrorSpy).toHaveBeenCalledTimes(2);
    });

    it("should not log errors when all required keys are present", async () => {
      import.meta.env.VITE_FIREBASE_API_KEY = "test-api-key";
      import.meta.env.VITE_FIREBASE_AUTH_DOMAIN = "test-auth-domain";
      import.meta.env.VITE_FIREBASE_PROJECT_ID = "test-project-id";
      await import("../lib/firebase");
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });
  });
});
