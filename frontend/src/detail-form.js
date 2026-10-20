export function createDetailForm(detail) {
  const review = detail.human_review
  return {
    tags: [...detail.tags],
    note: detail.note,
    accuracy: review?.accuracy ?? 3,
    completeness: review?.completeness ?? 3,
    refused: review?.refused ?? false,
    unsupported: review?.unsupported ?? false,
    factually_incorrect: review?.factually_incorrect ?? null,
    reviewer: review?.reviewer ?? '',
    review_note: review?.note ?? '',
  }
}
