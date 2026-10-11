import { StoryReader } from "@/components/stories/StoryReader";

export default async function StoryPage({
  params,
}: {
  params: Promise<{ storyId: string }>;
}) {
  const { storyId } = await params;
  return <StoryReader storyId={storyId} />;
}
