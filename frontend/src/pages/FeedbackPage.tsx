import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Star, Lightbulb, ThumbsUp } from "lucide-react";
import api from "../lib/api";

interface Review {
  id: string;
  review_type: string;
  rating: number | null;
  title: string;
  content: string;
  status: string;
  admin_response: string | null;
  is_public: boolean;
  created_at: string;
  user_display_name: string | null;
}

const TYPES = ["feedback", "testimonial", "feature_request"] as const;

export function FeedbackPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [type, setType] = useState<string>("feedback");
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const { data: myReviews } = useQuery<Review[]>({
    queryKey: ["my-reviews"],
    queryFn: () => api.get("/api/reviews/mine").then((r) => r.data),
  });

  const { data: publicReviews } = useQuery<Review[]>({
    queryKey: ["public-reviews"],
    queryFn: () => api.get("/api/reviews/public").then((r) => r.data),
  });

  const submit = useMutation({
    mutationFn: (data: { review_type: string; rating?: number; title: string; content: string }) =>
      api.post("/api/reviews/", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-reviews"] });
      setTitle("");
      setContent("");
      setRating(0);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit.mutate({
      review_type: type,
      ...(type !== "feature_request" && rating > 0 ? { rating } : {}),
      title,
      content,
    });
  };

  const typeConfig = {
    feedback: { icon: ThumbsUp, color: "bg-blue-50 border-blue-200 text-blue-700" },
    testimonial: { icon: Star, color: "bg-yellow-50 border-yellow-200 text-yellow-700" },
    feature_request: { icon: Lightbulb, color: "bg-purple-50 border-purple-200 text-purple-700" },
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-up">
      <h1 className="text-2xl font-bold">{t("feedback.title")}</h1>

      {/* Submit Form */}
      <div className="bg-[var(--color-bg-card)] rounded-xl border p-5 shadow-card">
        <h2 className="text-lg font-semibold mb-4">{t("feedback.submitTitle")}</h2>

        {/* Type Selector */}
        <div className="flex gap-2 mb-4">
          {TYPES.map((tp) => {
            const cfg = typeConfig[tp];
            const Icon = cfg.icon;
            return (
              <button
                key={tp}
                onClick={() => setType(tp)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm transition-colors ${
                  type === tp ? cfg.color : "bg-[var(--color-bg-app)] border-[var(--color-border-default)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-inset)]"
                }`}
              >
                <Icon className="w-4 h-4" />
                {t(`feedback.type_${tp}`)}
              </button>
            );
          })}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* Star Rating (for feedback/testimonial) */}
          {type !== "feature_request" && (
            <div className="flex items-center gap-1">
              <span className="text-sm text-[var(--color-text-secondary)] mr-2">{t("feedback.rating")}:</span>
              {[1, 2, 3, 4, 5].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setRating(s)}
                  onMouseEnter={() => setHoverRating(s)}
                  onMouseLeave={() => setHoverRating(0)}
                  className="focus:outline-none"
                >
                  <Star
                    className={`w-6 h-6 transition-colors ${
                      s <= (hoverRating || rating) ? "text-yellow-400 fill-yellow-400" : "text-[var(--color-border-strong)]"
                    }`}
                  />
                </button>
              ))}
            </div>
          )}

          <input
            type="text"
            placeholder={t("feedback.titlePlaceholder")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={200}
            className="w-full border border-[var(--color-border-strong)] bg-[var(--color-bg-app)] text-[var(--color-text-primary)] rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[var(--color-accent)] focus:border-[var(--color-accent)] outline-none"
          />

          <textarea
            placeholder={t("feedback.contentPlaceholder")}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            required
            maxLength={2000}
            rows={4}
            className="w-full border border-[var(--color-border-strong)] bg-[var(--color-bg-app)] text-[var(--color-text-primary)] rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[var(--color-accent)] focus:border-[var(--color-accent)] outline-none resize-none"
          />

          <button
            type="submit"
            disabled={submit.isPending || !title || !content}
            className="px-4 py-2 bg-[var(--color-accent)] text-white text-sm font-medium rounded-lg hover:bg-[var(--color-accent-hover)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submit.isPending ? t("common.saving") : t("feedback.submit")}
          </button>

          {submit.isSuccess && (
            <p className="text-sm text-green-600">{t("feedback.submitted")}</p>
          )}
        </form>
      </div>

      {/* My Reviews */}
      {(myReviews ?? []).length > 0 && (
        <div className="bg-[var(--color-bg-card)] rounded-xl border p-5 shadow-card">
          <h2 className="text-lg font-semibold mb-3">{t("feedback.myReviews")}</h2>
          <div className="space-y-3">
            {myReviews!.map((r) => (
              <div key={r.id} className="border border-[var(--color-border-default)] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    typeConfig[r.review_type as keyof typeof typeConfig]?.color ?? "bg-[var(--color-bg-inset)] text-[var(--color-text-secondary)]"
                  }`}>
                    {t(`feedback.type_${r.review_type}`)}
                  </span>
                  {r.rating && (
                    <span className="flex items-center gap-0.5 text-yellow-500">
                      {Array.from({ length: r.rating }).map((_, i) => (
                        <Star key={i} className="w-3 h-3 fill-current" />
                      ))}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    r.status === "approved" || r.status === "done" ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400" :
                    r.status === "rejected" ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400" :
                    "bg-[var(--color-bg-inset)] text-[var(--color-text-secondary)]"
                  }`}>{r.status}</span>
                </div>
                <p className="text-sm font-medium">{r.title}</p>
                <p className="text-sm text-[var(--color-text-secondary)]">{r.content}</p>
                {r.admin_response && (
                  <div className="mt-2 pl-3 border-l-2 border-blue-200">
                    <p className="text-xs text-blue-600 font-medium">{t("feedback.adminReply")}:</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">{r.admin_response}</p>
                  </div>
                )}
                <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{new Date(r.created_at).toLocaleDateString()}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Public Testimonials */}
      {(publicReviews ?? []).length > 0 && (
        <div className="bg-[var(--color-bg-card)] rounded-xl border p-5 shadow-card">
          <h2 className="text-lg font-semibold mb-3">{t("feedback.publicTestimonials")}</h2>
          <div className="space-y-3">
            {publicReviews!.map((r) => (
              <div key={r.id} className="border border-[var(--color-border-default)] rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm">{r.user_display_name || t("feedback.anonymous")}</span>
                  {r.rating && (
                    <span className="flex items-center gap-0.5 text-yellow-500">
                      {Array.from({ length: r.rating }).map((_, i) => (
                        <Star key={i} className="w-3 h-3 fill-current" />
                      ))}
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium">{r.title}</p>
                <p className="text-sm text-[var(--color-text-secondary)]">{r.content}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
