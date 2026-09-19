//! Stable entry point. /reload replaces the profile plugins from fresh source.
import { plugins } from "yuke";
import { profileReloader } from "./plugins/profile-reloader.js";

plugins.use(profileReloader);
