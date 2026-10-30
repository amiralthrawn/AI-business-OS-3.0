import CreateTaskButton from "@/components/actions/CreateTaskButton";
import EmailComposer from "@/components/shared/EmailComposer";
import Card from "@/components/ui/Card";
import type { LinkedContact, RelatedEntityType } from "@/lib/types";

interface ContactCardProps {
  contact: LinkedContact;
  entityName: string;
  entityType: RelatedEntityType;
  entityId: string;
}

// A real person at this Supplier/Customer (Step 27) -- always sourced from
// `Contact`, never invented. Offers the two real actions the product
// supports: preparing an email (mailto:, never auto-sent) and creating a
// task, both tied back to the entity this contact belongs to.
export default function ContactCard({ contact, entityName, entityType, entityId }: ContactCardProps) {
  return (
    <Card className="p-5">
      <p className="font-semibold text-[14.5px] text-text">{contact.name}</p>
      <p className="mt-0.5 text-[12.5px] text-text-faint">
        {contact.role ?? "Rôle inconnu"} &middot; {entityName}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {contact.email && (
          <EmailComposer
            to={contact.email}
            toName={contact.name}
            defaultSubject={`Contact — ${contact.name}`}
            defaultBody={`Bonjour ${contact.name.split(" ")[0]},\n\n`}
          />
        )}
        <CreateTaskButton defaultTitle={`Contacter ${contact.name}`} relatedEntityType={entityType} relatedEntityId={entityId} />
      </div>
    </Card>
  );
}
