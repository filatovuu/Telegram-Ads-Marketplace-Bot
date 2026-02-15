import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/context/AuthContext";

vi.mock("@/api/auth", () => ({
  loginWithInitData: vi.fn(),
  getMe: vi.fn(),
  switchRole: vi.fn(),
  updateLocale: vi.fn(),
}));

import { loginWithInitData, getMe, switchRole, updateLocale } from "@/api/auth";

const mockUser = {
  id: 1,
  telegram_id: 123456,
  username: "testuser",
  first_name: "Test",
  active_role: "advertiser" as const,
  locale: "en",
  timezone: "UTC",
  created_at: "2025-01-01T00:00:00Z",
};

function TestConsumer() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="authenticated">{String(auth.authenticated)}</span>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="role">{auth.user?.active_role ?? "none"}</span>
      <span data-testid="error">{auth.error ?? ""}</span>
      <button data-testid="login" onClick={() => auth.login("init_data_string")} />
      <button data-testid="switch-role" onClick={() => auth.setRole("owner")} />
      <button data-testid="set-locale" onClick={() => auth.setLocale("ru")} />
      <button data-testid="logout" onClick={auth.logout} />
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(getMe).mockRejectedValue(new Error("no session"));
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts unauthenticated when no token", async () => {
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("role").textContent).toBe("none");
  });

  it("restores session from existing token", async () => {
    localStorage.setItem("token", "existing-jwt");
    vi.mocked(getMe).mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("role").textContent).toBe("advertiser");
  });

  it("clears invalid token on session restore failure", async () => {
    localStorage.setItem("token", "bad-jwt");
    vi.mocked(getMe).mockRejectedValue(new Error("invalid token"));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(localStorage.getItem("token")).toBeNull();
  });

  it("login stores token and sets user", async () => {
    vi.mocked(loginWithInitData).mockResolvedValue({
      access_token: "new-jwt",
      user: mockUser,
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    await act(async () => {
      screen.getByTestId("login").click();
    });

    expect(localStorage.getItem("token")).toBe("new-jwt");
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("role").textContent).toBe("advertiser");
  });

  it("login failure sets error", async () => {
    vi.mocked(loginWithInitData).mockRejectedValue(new Error("Auth failed"));

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    await act(async () => {
      screen.getByTestId("login").click();
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("error").textContent).toBe("Auth failed");
  });

  it("setRole updates user role", async () => {
    localStorage.setItem("token", "jwt");
    vi.mocked(getMe).mockResolvedValue(mockUser);
    vi.mocked(switchRole).mockResolvedValue({ ...mockUser, active_role: "owner" });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("true");
    });

    await act(async () => {
      screen.getByTestId("switch-role").click();
    });

    expect(switchRole).toHaveBeenCalledWith("owner");
    expect(screen.getByTestId("role").textContent).toBe("owner");
  });

  it("setLocale updates user locale", async () => {
    localStorage.setItem("token", "jwt");
    vi.mocked(getMe).mockResolvedValue(mockUser);
    vi.mocked(updateLocale).mockResolvedValue({ ...mockUser, locale: "ru" });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("true");
    });

    await act(async () => {
      screen.getByTestId("set-locale").click();
    });

    expect(updateLocale).toHaveBeenCalledWith("ru");
  });

  it("logout clears token and user", async () => {
    localStorage.setItem("token", "jwt");
    vi.mocked(getMe).mockResolvedValue(mockUser);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("authenticated").textContent).toBe("true");
    });

    await act(async () => {
      screen.getByTestId("logout").click();
    });

    expect(localStorage.getItem("token")).toBeNull();
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("throws when useAuth is used outside AuthProvider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow(
      "useAuth must be used within AuthProvider",
    );
    spy.mockRestore();
  });
});
