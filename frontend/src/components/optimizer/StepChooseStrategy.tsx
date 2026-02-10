import { useTranslation } from "react-i18next";
import { TrendingDown, Zap, Brain } from "lucide-react";

interface Props {
  selected: string;
  onChange: (strategy: string) => void;
}

const strategies = [
  {
    id: "smart_hybrid",
    icon: Brain,
    color: "from-indigo-500 to-purple-600",
    borderColor: "border-indigo-300 bg-indigo-50",
    recommended: true,
  },
  {
    id: "avalanche",
    icon: TrendingDown,
    color: "from-blue-500 to-cyan-600",
    borderColor: "border-blue-300 bg-blue-50",
    recommended: false,
  },
  {
    id: "snowball",
    icon: Zap,
    color: "from-green-500 to-emerald-600",
    borderColor: "border-green-300 bg-green-50",
    recommended: false,
  },
];

export function StepChooseStrategy({ selected, onChange }: Props) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-[var(--color-text-primary)]">{t("optimizer.choosePriority")}</h2>

      <div className="space-y-3">
        {strategies.map((s) => (
          <label
            key={s.id}
            className={`flex items-center gap-4 p-5 rounded-xl border-2 cursor-pointer transition-all ${
              selected === s.id ? s.borderColor : "border-[var(--color-border-default)] hover:border-[var(--color-border-strong)]"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              value={s.id}
              checked={selected === s.id}
              onChange={() => onChange(s.id)}
              className="sr-only"
            />
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${s.color} flex items-center justify-center`}>
              <s.icon className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-[var(--color-text-primary)]">
                  {t(`optimizer.${s.id === "smart_hybrid" ? "smartHybrid" : s.id}`)}
                </span>
                {s.recommended && (
                  <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
                    {t("optimizer.strategy.recommended")}
                  </span>
                )}
              </div>
              <p className="text-sm text-[var(--color-text-secondary)] mt-0.5">
                {t(`optimizer.strategy.${s.id === "smart_hybrid" ? "smartHybridDesc" : s.id + "Desc"}`)}
              </p>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
