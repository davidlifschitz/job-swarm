import SwiftUI

public enum AppTheme {
    public static let background = Color(red: 0.97, green: 0.98, blue: 0.99)
    public static let surface = Color.white
    public static let sidebar = Color(red: 0.08, green: 0.12, blue: 0.20)
    public static let accent = Color(red: 0.12, green: 0.35, blue: 0.88)
    public static let referral = Color(red: 0.05, green: 0.55, blue: 0.32)
    public static let muted = Color(red: 0.34, green: 0.39, blue: 0.47)
    public static let textPrimary = Color(red: 0.09, green: 0.11, blue: 0.15)
    public static let textOnSidebar = Color.white
    public static let border = Color(red: 0.82, green: 0.86, blue: 0.91)
}

public struct AppBorderedButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.medium))
            .foregroundStyle(AppTheme.accent)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(AppTheme.surface)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(
                        AppTheme.accent.opacity(configuration.isPressed ? 0.45 : 1),
                        lineWidth: 1
                    )
            )
            .opacity(configuration.isPressed ? 0.85 : 1)
    }
}

public struct AppProminentButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Color.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 6)
                    .fill(AppTheme.accent.opacity(configuration.isPressed ? 0.82 : 1))
            )
    }
}

public struct AppFilterChipStyle: ButtonStyle {
    private let selected: Bool

    public init(selected: Bool) {
        self.selected = selected
    }

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.caption.weight(.semibold))
            .foregroundStyle(selected ? Color.white : AppTheme.textPrimary)
            .padding(.horizontal, 12)
            .padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(selected ? AppTheme.accent : AppTheme.background)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(selected ? AppTheme.accent : AppTheme.border, lineWidth: 1)
            )
            .opacity(configuration.isPressed ? 0.88 : 1)
    }
}

public struct AppLinkButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.medium))
            .foregroundStyle(AppTheme.accent)
            .underline(configuration.isPressed)
    }
}

public struct MainContentStyle: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .foregroundStyle(AppTheme.textPrimary)
            .background(AppTheme.background)
            .preferredColorScheme(.light)
            .tint(AppTheme.accent)
            .textSelection(.enabled)
    }
}

public struct SurfaceCardStyle: ViewModifier {
    public func body(content: Content) -> some View {
        content
            .padding(16)
            .background(AppTheme.surface)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(AppTheme.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

extension View {
    public func mainContentStyle() -> some View {
        modifier(MainContentStyle())
    }

    public func surfaceCardStyle() -> some View {
        modifier(SurfaceCardStyle())
    }

    public func appBorderedButton() -> some View {
        buttonStyle(AppBorderedButtonStyle())
    }

    public func appProminentButton() -> some View {
        buttonStyle(AppProminentButtonStyle())
    }

    public func appLinkButton() -> some View {
        buttonStyle(AppLinkButtonStyle())
    }

    public func appFilterChip(selected: Bool) -> some View {
        buttonStyle(AppFilterChipStyle(selected: selected))
    }
}