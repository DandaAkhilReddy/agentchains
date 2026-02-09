/// <reference types="vitest/globals" />
import type { User } from "firebase/auth";
import { useAuthStore } from "../store/authStore";

// Reset store before each test
beforeEach(() => {
  useAuthStore.setState({ user: null, loading: true });
});

describe("authStore", () => {
  it("has correct initial state: user null, loading true", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(true);
  });

  it("setUser sets user and loading to false", () => {
    const fakeUser = { uid: "abc123", email: "test@example.com" } as unknown as User;
    useAuthStore.getState().setUser(fakeUser);

    const state = useAuthStore.getState();
    expect(state.user).toBe(fakeUser);
    expect(state.loading).toBe(false);
  });

  it("setUser with null clears user and sets loading false", () => {
    // First set a user
    const fakeUser = { uid: "abc123" } as unknown as User;
    useAuthStore.getState().setUser(fakeUser);
    expect(useAuthStore.getState().user).toBe(fakeUser);

    // Then clear
    useAuthStore.getState().setUser(null);
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(false);
  });

  it("setLoading updates loading independently", () => {
    useAuthStore.getState().setLoading(false);
    expect(useAuthStore.getState().loading).toBe(false);

    useAuthStore.getState().setLoading(true);
    expect(useAuthStore.getState().loading).toBe(true);
  });

  it("setLoading does not affect user", () => {
    const fakeUser = { uid: "abc123" } as unknown as User;
    useAuthStore.getState().setUser(fakeUser);

    useAuthStore.getState().setLoading(true);
    expect(useAuthStore.getState().user).toBe(fakeUser);
  });

  it("multiple setUser calls update correctly", () => {
    const user1 = { uid: "user1" } as unknown as User;
    const user2 = { uid: "user2" } as unknown as User;

    useAuthStore.getState().setUser(user1);
    expect(useAuthStore.getState().user).toBe(user1);

    useAuthStore.getState().setUser(user2);
    expect(useAuthStore.getState().user).toBe(user2);
  });
});
