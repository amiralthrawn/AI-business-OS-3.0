import CalendarView from "@/components/calendar/CalendarView";
import PageHeader from "@/components/ui/PageHeader";

export const dynamic = "force-dynamic";

export default function CalendarPage() {
  return (
    <main className="space-y-6 p-6 md:p-10">
      <PageHeader title="Calendrier" description="Ce qui s'est passé et ce qui arrive. L'IA le remplit depuis vos données, vous pouvez y ajouter vos événements." />
      <CalendarView />
    </main>
  );
}
