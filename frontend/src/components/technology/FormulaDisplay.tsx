export interface FormulaTerm {
  weight: number;
  label: string;
  value?: number;
  color: string;
}

interface Props {
  terms: FormulaTerm[];
  bonusTerms?: FormulaTerm[];
  result?: number;
  title?: string;
  className?: string;
}

function WeightPill({ weight, color }: { weight: number; color: string }) {
  return (
    <span
      className="rounded px-1.5 py-0.5 font-mono text-xs font-bold"
      style={{
        backgroundColor: `${color}1a`,
        color,
      }}
    >
      {weight}
    </span>
  );
}

function TermItem({
  term,
  isBonus,
}: {
  term: FormulaTerm;
  isBonus?: boolean;
}) {
  const pillColor = isBonus ? "#d97706" : term.color;
  return (
    <span className="inline-flex items-center gap-1">
      {isBonus && (
        <span className="font-mono text-xs text-[#d97706] font-bold">+</span>
      )}
      <WeightPill weight={term.weight} color={pillColor} />
      <span className="font-mono text-xs text-text-secondary">
        {"× "}
        {term.label}
      </span>
    </span>
  );
}

function ComputedRow({ term, isBonus }: { term: FormulaTerm; isBonus?: boolean }) {
  if (term.value === undefined) return null;
  const pillColor = isBonus ? "#d97706" : term.color;
  const computed = +(term.weight * term.value).toFixed(4);
  return (
    <span className="inline-flex items-center gap-1">
      {isBonus && (
        <span className="font-mono text-xs text-[#d97706] font-bold">+</span>
      )}
      <span
        className="font-mono text-xs font-bold"
        style={{ color: pillColor }}
      >
        {term.weight}
      </span>
      <span className="font-mono text-xs text-text-muted">{"× "}{term.value}</span>
      <span className="font-mono text-xs text-text-secondary">
        = {computed}
      </span>
    </span>
  );
}

/** Renders a mathematical formula with color-coded weighted terms. */
export default function FormulaDisplay({
  terms,
  bonusTerms,
  result,
  title,
  className = "",
}: Props) {
  const allTerms = terms.concat(bonusTerms ?? []);
  const hasValues = allTerms.some((t) => t.value !== undefined);

  return (
    <div className={`space-y-2 ${className}`}>
      {title && (
        <h4 className="font-semibold text-sm text-text-primary">{title}</h4>
      )}

      {/* Formula row */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs font-semibold text-text-primary">
          Score =
        </span>
        {terms.map((term, i) => (
          <span key={term.label} className="inline-flex items-center gap-1.5">
            {i > 0 && (
              <span className="font-mono text-xs text-text-muted">+</span>
            )}
            <TermItem term={term} />
          </span>
        ))}
        {bonusTerms?.map((term) => (
          <TermItem key={term.label} term={term} isBonus />
        ))}
      </div>

      {/* Computed values row */}
      {hasValues && (
        <div className="flex flex-wrap items-center gap-1.5 pl-[3.25rem]">
          {terms.map((term, i) => (
            <span key={term.label} className="inline-flex items-center gap-1.5">
              {i > 0 && (
                <span className="font-mono text-xs text-text-muted">+</span>
              )}
              <ComputedRow term={term} />
            </span>
          ))}
          {bonusTerms?.map((term) => (
            <ComputedRow key={term.label} term={term} isBonus />
          ))}
        </div>
      )}

      {/* Result pill */}
      {result !== undefined && (
        <div className="flex items-center gap-2 pt-1">
          <span className="text-xs text-text-muted">=</span>
          <span className="rounded-lg px-3 py-1 bg-primary-glow text-primary font-mono font-bold">
            {result}
          </span>
        </div>
      )}
    </div>
  );
}
