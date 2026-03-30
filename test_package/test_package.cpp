#include "Jolt/Jolt.h"
#include "Jolt/RegisterTypes.h"
#include "Jolt/Core/Factory.h"
#include "Jolt/Core/TempAllocator.h"
#include "Jolt/Core/JobSystemThreadPool.h"
#include "Jolt/Physics/PhysicsSystem.h"
#include "Jolt/Physics/Collision/Shape/BoxShape.h"
#include "Jolt/Physics/Collision/Shape/SphereShape.h"
#include "Jolt/Physics/Body/BodyCreationSettings.h"

#include <cstdlib>
#include <iostream>
#include <thread>

JPH_SUPPRESS_WARNINGS

using namespace JPH;
using namespace JPH::literals;

namespace Layers
{
    static constexpr ObjectLayer STATIC = 0u;
    static constexpr ObjectLayer DYNAMIC = 1u;
    static constexpr ObjectLayer NUM = 2u;
};

class BPLayerImpl final : public BroadPhaseLayerInterface
{
    BroadPhaseLayer mMap[Layers::NUM];
public:
    BPLayerImpl()
    {
        mMap[Layers::STATIC] = BroadPhaseLayer(0u);
        mMap[Layers::DYNAMIC] = BroadPhaseLayer(1u);
    }

    uint GetNumBroadPhaseLayers() const override
    {
        return Layers::NUM;
    }

    BroadPhaseLayer GetBroadPhaseLayer(ObjectLayer inLayer) const override
    {
        return mMap[inLayer];
    }
};

class ObjVsBPFilter : public ObjectVsBroadPhaseLayerFilter
{
public:
    bool ShouldCollide(ObjectLayer inLayer, BroadPhaseLayer inBPLayer) const override
    {
        if (inLayer == Layers::STATIC)
            return inBPLayer == BroadPhaseLayer(1u);
        return true;
    }
};

class ObjPairFilter : public ObjectLayerPairFilter
{
public:
    bool ShouldCollide(ObjectLayer inA, ObjectLayer inB) const override
    {
        if (inA == Layers::STATIC)
            return inB == Layers::DYNAMIC;
        return true;
    }
};

int main()
{
    RegisterDefaultAllocator();
    Factory::sInstance = new Factory();
    RegisterTypes();

    TempAllocatorImpl temp_allocator(1u * 1024u * 1024u);
    JobSystemThreadPool job_system(cMaxPhysicsJobs, cMaxPhysicsBarriers,
                                   std::max(1u, std::thread::hardware_concurrency() - 1u));

    BPLayerImpl bp_layer;
    ObjVsBPFilter obj_vs_bp;
    ObjPairFilter obj_pair;

    PhysicsSystem physics;
    physics.Init(64u, 0u, 64u, 64u, bp_layer, obj_vs_bp, obj_pair);

    BodyInterface &bodies = physics.GetBodyInterface();

    // Static floor at y = -1
    BoxShapeSettings floor_shape(Vec3(100.0f, 1.0f, 100.0f));
    floor_shape.SetEmbedded();
    Body *floor = bodies.CreateBody(
        BodyCreationSettings(floor_shape.Create().Get(),
                             RVec3(0.0_r, -1.0_r, 0.0_r), Quat::sIdentity(),
                             EMotionType::Static, Layers::STATIC));
    bodies.AddBody(floor->GetID(), EActivation::DontActivate);

    // Dynamic sphere at y = 2
    BodyID sphere = bodies.CreateAndAddBody(
        BodyCreationSettings(new SphereShape(0.5f),
                             RVec3(0.0_r, 2.0_r, 0.0_r), Quat::sIdentity(),
                             EMotionType::Dynamic, Layers::DYNAMIC),
        EActivation::Activate);
    bodies.SetLinearVelocity(sphere, Vec3(0.0f, -5.0f, 0.0f));

    physics.OptimizeBroadPhase();

    // Simulate 8 steps at 60 Hz
    const float dt = 1.0f / 60.0f;
    for (int step = 1; step <= 8; ++step)
    {
        physics.Update(dt, 1, &temp_allocator, &job_system);
        RVec3 pos = bodies.GetCenterOfMassPosition(sphere);
        std::cout << "Step " << step << ": y = " << pos.GetY() << std::endl;
    }

    // Cleanup
    bodies.RemoveBody(sphere);
    bodies.DestroyBody(sphere);
    bodies.RemoveBody(floor->GetID());
    bodies.DestroyBody(floor->GetID());

    UnregisterTypes();
    delete Factory::sInstance;
    Factory::sInstance = nullptr;

    return EXIT_SUCCESS;
}
