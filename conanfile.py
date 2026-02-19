from conan import ConanFile
from conan.tools.build import check_min_cppstd
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get, rmdir, rm, export_conandata_patches, apply_conandata_patches
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
import os

required_conan_version = ">=2.0.9"


class JoltPhysicsConan(ConanFile):
    name = "joltphysics"
    description = (
        "A multi core friendly rigid body physics and collision detection "
        "library, written in C++, suitable for games and VR applications."
    )
    license = "MIT"
    topics = ("physics", "simulation", "physics-engine", "physics-simulation", "rigid-body", "game", "collision")
    homepage = "https://github.com/jrouwe/JoltPhysics"
    url = "https://github.com/triadastudio/conan-joltphysics"
    version = "5.2.0"

    package_type = "library"
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "debug_renderer": [True, False],
        "profiler": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "debug_renderer": False,
        "profiler": False,
    }
    implements = ["auto_shared_fpic"]

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def build_requirements(self):
        self.tool_requires("cmake/[>=3.30 <4]")

    def validate(self):
        check_min_cppstd(self, 17)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)
        apply_conandata_patches(self)

    def _effective_build_type(self):
        """Map Conan build types to Jolt-supported CMake build types.

        Jolt Physics' supports Debug, Release, and Distribution
        configurations in its CMakeLists.txt.
        When MSVC is used with multi-config generators, building with RelWithDebInfo
        fails with:
            error MSB8013: This project doesn't contain the Configuration
            and Platform combination of RelWithDebInfo|x64

        This method maps:
            Debug          -> Debug
            Release        -> Release
            RelWithDebInfo -> Release
            MinSizeRel     -> Release
        """
        bt = str(self.settings.build_type)
        if bt in ("RelWithDebInfo", "MinSizeRel"):
            return "Release"
        return bt

    def generate(self):
        tc = CMakeToolchain(self)

        # --- Build-type remapping for Jolt compatibility ---
        effective_bt = self._effective_build_type()
        if str(self.settings.build_type) != effective_bt:
            # For single-config generators (Ninja, Unix Makefiles), override
            # CMAKE_BUILD_TYPE so CMake uses a configuration Jolt supports.
            tc.cache_variables["CMAKE_BUILD_TYPE"] = effective_bt

            # For multi-config generators (Visual Studio, Ninja Multi-Config),
            # restrict the set of configurations to what Jolt supports.
            # The CMakeToolchain already writes CMAKE_CONFIGURATION_TYPES, 
            # but Jolt's CMakeLists.txt overwrites it with its own set;
            # by injecting the build type here the generator selects the
            # correct configuration.
            tc.cache_variables["CMAKE_CONFIGURATION_TYPES"] = "Debug;Release;Distribution"

        tc.cache_variables["TARGET_UNIT_TESTS"] = False
        tc.cache_variables["TARGET_HELLO_WORLD"] = False
        tc.cache_variables["TARGET_PERFORMANCE_TEST"] = False
        tc.cache_variables["TARGET_SAMPLES"] = False
        tc.cache_variables["TARGET_VIEWER"] = False
        tc.cache_variables["CROSS_PLATFORM_DETERMINISTIC"] = False
        tc.cache_variables["INTERPROCEDURAL_OPTIMIZATION"] = False
        tc.cache_variables["GENERATE_DEBUG_SYMBOLS"] = False
        tc.cache_variables["ENABLE_ALL_WARNINGS"] = False
        tc.cache_variables["OVERRIDE_CXX_FLAGS"] = False
        tc.cache_variables["DEBUG_RENDERER_IN_DEBUG_AND_RELEASE"] = \
            bool(self.options.debug_renderer)
        tc.cache_variables["PROFILER_IN_DEBUG_AND_RELEASE"] = \
            bool(self.options.profiler)
        if is_msvc(self):
            tc.cache_variables["USE_STATIC_MSVC_RUNTIME_LIBRARY"] = is_msvc_static_runtime(self)
        tc.generate()

    def build(self):
        cmake = CMake(self)

        # Jolt's CMakeLists.txt lives in the Build/ subdirectory.
        build_script = os.path.join(self.source_folder, "Build")

        cmake.configure(build_script_folder=build_script)

        effective_bt = self._effective_build_type()
        if str(self.settings.build_type) != effective_bt:
            cmake.build(build_type=effective_bt)
        else:
            cmake.build()

    def package(self):
        copy(self, "LICENSE", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)

        effective_bt = self._effective_build_type()
        if str(self.settings.build_type) != effective_bt:
            cmake.install(build_type=effective_bt)
        else:
            cmake.install()

        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rm(self, "*.cmake", os.path.join(self.package_folder, "include", "Jolt"))

    def package_info(self):
        self.cpp_info.libs = ["Jolt"]
        self.cpp_info.set_property("cmake_file_name", "Jolt")
        self.cpp_info.set_property("cmake_target_name", "Jolt::Jolt")
        # INFO: The CMake option ENABLE_OBJECT_STREAM is enabled by default and defines JPH_OBJECT_STREAM as public
        # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Build/CMakeLists.txt#L95C8-L95C28
        self.cpp_info.defines = ["JPH_OBJECT_STREAM"]
        # INFO: Public defines exposed in include/Jolt/Jolt.cmake
        # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Build/CMakeLists.txt#L51
        if self.settings.arch in ["x86_64", "x86"]:
            self.cpp_info.defines.extend(["JPH_USE_AVX2", "JPH_USE_AVX", "JPH_USE_SSE4_1",
                                          "JPH_USE_SSE4_2", "JPH_USE_LZCNT", "JPH_USE_TZCNT",
                                          "JPH_USE_F16C", "JPH_USE_FMADD"])
        if is_msvc(self):
            # INFO: Floating point exceptions are enabled by default
            # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Build/CMakeLists.txt#L37
            # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Jolt/Jolt.cmake#L529
            self.cpp_info.defines.append("JPH_FLOATING_POINT_EXCEPTIONS_ENABLED")

        if self.options.shared:
            # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Jolt/Jolt.cmake#L495
            self.cpp_info.defines.append("JPH_SHARED_LIBRARY")

        if self.options.debug_renderer:
            self.cpp_info.defines.append("JPH_DEBUG_RENDERER")

        if self.options.profiler:
            self.cpp_info.defines.append("JPH_PROFILE_ENABLED")

        # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Build/CMakeLists.txt#L48
        # https://github.com/jrouwe/JoltPhysics/blob/v5.2.0/Jolt/Jolt.cmake#L554
        self.cpp_info.defines.append("JPH_OBJECT_LAYER_BITS=16")

        if self.settings.os in ["Linux", "FreeBSD"]:
            self.cpp_info.system_libs.append("pthread")

    def compatibility(self):
        """Allow a package built with Release to satisfy RelWithDebInfo
        and MinSizeRel consumers.

        This is safe because we build the Release configuration when the user
        requests RelWithDebInfo (see _effective_build_type), so the resulting
        package IS a Release build and binary-compatible with RelWithDebInfo
        consumers.
        """
        if self.settings.build_type == "RelWithDebInfo":
            return [{"settings": [("build_type", "Release")]}]
        if self.settings.build_type == "MinSizeRel":
            return [{"settings": [("build_type", "Release")]}]
        return []

