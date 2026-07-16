using RimWorld;
using System.Linq;
using Verse;

// RimWorld constructs the component declared in Buildings.xml and invokes it on
// the parent shelf's rare-tick schedule. Keeping the behavior in a ThingComp
// leaves storage semantics to the game's normal shelf implementation; this
// assembly only supplies the destructive step layered on top.
namespace VoidShelf
{
    /// <summary>Provides the load-time integration point for the mod.</summary>
    public class VoidShelfMod : Mod
    {
        public VoidShelfMod(ModContentPack content) : base(content)
        {
            Log.Message("[VoidShelf] VoidShelfMod loaded.");
        }
    }

    /// <summary>
    /// Bridges the XML component declaration to its runtime implementation.
    /// RimWorld creates this properties object while resolving the ThingDef.
    /// </summary>
    public class CompProperties_DestroyerShelf : CompProperties
    {
        public CompProperties_DestroyerShelf()
        {
            this.compClass = typeof(CompDestroyerShelf);
        }
    }

    /// <summary>Destroys the items currently held by the component's shelf.</summary>
    public class CompDestroyerShelf : ThingComp
    {
        public override void CompTickRare()
        {
            base.CompTickRare();

            // A parent without a slot group has no storage inventory to process.
            // Treat that valid absence as a no-op rather than assuming setup.
            var slotGroup = parent.GetSlotGroup();
            if (slotGroup == null) return;

            // Destroy mutates HeldThings, so iterate over a stable snapshot. The
            // parent may appear in the slot group and must never destroy itself.
            foreach (Thing thing in slotGroup.HeldThings.ToList())
            {
                if (thing != parent)
                {
                    // Destroy is deliberately irreversible: the shelf is an item
                    // sink rather than a container with a recoverable inventory.
                    Log.Message($"[VoidShelf] Destroying: {thing.Label} at {thing.Position}");
                    thing.Destroy();
                }
            }
        }
    }
}
