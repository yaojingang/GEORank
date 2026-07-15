/**
 * GEOrank - Tailwind CSS 配置
 * GEO 智搜优化引擎 前端系统
 * 版本: 1.0.0
 */

tailwind.config = {
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                // 主色调
                "primary": "#2563EB",
                "primary-dark": "#1E40AF",
                "primary-light": "#3B82F6",
                "secondary": "#2563EB",

                // 错误状态
                "error": "#ba1a1a",
                "error-container": "#ffdad6",

                // 表面颜色
                "surface": "#ffffff",
                "surface-variant": "#dde4e5",
                "surface-container": "#ebeeef",
                "surface-container-low": "#f2f4f4",
                "surface-container-high": "#e4e9ea",
                "surface-container-highest": "#dde4e5",
                "surface-container-lowest": "#ffffff",
                "surface-bright": "#f9f9f9",
                "surface-dim": "#d3dbdd",
                "surface-tint": "#2563EB",

                // 背景
                "background": "#ffffff",

                // 文字颜色
                "on-primary": "#ffffff",
                "on-surface": "#2d3435",
                "on-surface-variant": "#596061",
                "on-background": "#2d3435",
                "on-secondary": "#ffffff",
                "on-error": "#ffffff",

                // 轮廓
                "outline": "#757c7d",
                "outline-variant": "#acb3b4",

                // 容器颜色
                "primary-container": "#DBEAFE",
                "on-primary-container": "#1E40AF",
                "secondary-container": "#DBEAFE",
                "on-secondary-container": "#1E40AF",

                // 反向颜色
                "inverse-surface": "#0c0f0f",
                "inverse-on-surface": "#9c9d9d",
                "inverse-primary": "#b4c5ff",

                // 三级颜色
                "tertiary": "#006d4a",
                "tertiary-container": "#69f6b8",
                "on-tertiary": "#e6ffee",
                "on-tertiary-container": "#005a3c"
            },
            borderRadius: {
                "DEFAULT": "4px",
                "sm": "2px",
                "md": "4px",
                "lg": "8px",
                "xl": "12px",
                "2xl": "16px",
                "3xl": "24px",
                "full": "9999px"
            },
            fontFamily: {
                "headline": ["Manrope", "system-ui", "sans-serif"],
                "body": ["Inter", "system-ui", "sans-serif"],
                "label": ["Inter", "system-ui", "sans-serif"],
                "manrope": ["Manrope", "system-ui", "sans-serif"],
                "inter": ["Inter", "system-ui", "sans-serif"]
            },
            fontSize: {
                "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
                "xs": ["0.75rem", { lineHeight: "1rem" }],
                "sm": ["0.875rem", { lineHeight: "1.25rem" }],
                "base": ["1rem", { lineHeight: "1.5rem" }],
                "lg": ["1.125rem", { lineHeight: "1.75rem" }],
                "xl": ["1.25rem", { lineHeight: "1.75rem" }],
                "2xl": ["1.5rem", { lineHeight: "2rem" }],
                "3xl": ["1.875rem", { lineHeight: "2.25rem" }],
                "4xl": ["2.25rem", { lineHeight: "2.5rem" }],
                "5xl": ["3rem", { lineHeight: "1.1" }],
                "6xl": ["3.75rem", { lineHeight: "1.1" }]
            },
            spacing: {
                "18": "4.5rem",
                "22": "5.5rem",
                "30": "7.5rem"
            },
            maxWidth: {
                "8xl": "88rem",
                "9xl": "96rem"
            },
            boxShadow: {
                "soft": "0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)",
                "card": "0 10px 40px rgba(25, 27, 35, 0.04)",
                "hover": "0 20px 50px rgba(25, 27, 35, 0.08)",
                "nav": "0 10px 40px rgba(25, 27, 35, 0.04)"
            },
            animation: {
                "fade-in": "fadeIn 0.3s ease-out forwards",
                "slide-up": "slideUp 0.3s ease-out forwards",
                "scale-in": "scaleIn 0.2s ease-out forwards"
            },
            keyframes: {
                fadeIn: {
                    "0%": { opacity: "0" },
                    "100%": { opacity: "1" }
                },
                slideUp: {
                    "0%": { opacity: "0", transform: "translateY(10px)" },
                    "100%": { opacity: "1", transform: "translateY(0)" }
                },
                scaleIn: {
                    "0%": { opacity: "0", transform: "scale(0.95)" },
                    "100%": { opacity: "1", transform: "scale(1)" }
                }
            },
            transitionDuration: {
                "250": "250ms",
                "350": "350ms"
            },
            backdropBlur: {
                "xs": "2px",
                "xl": "20px"
            }
        }
    },
    plugins: []
};
