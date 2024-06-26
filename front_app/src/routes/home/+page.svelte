<script
  src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
  lang="ts"
>
  import "../../app.css";
  import { onMount } from "svelte";
  import {
    get_cookie_values,
    logout_user,
    is_logged,
    SERVER_URL,
    downloadVideo,
    redirectToHome,
    redirectToLogin,
    redirectToSignUp,
    redirectToProfile,
    redirectToUpload,
    redirectToUserProfile,
    handleUpVote,
    get_cookie,
    handleCommentButton,
    deleteComment,
    fetchProfilePicture,
    timeAgo,
    removeCookie,
  } from "../../lib/utils";
  import { find_closest_waypoint, update_map } from "../../lib/gpx_utils";
  import type { Waypoint_upload } from "../../lib/gpx_utils";
  import type { User, Video, Upvote, Comment } from "../../lib/utils";

  let waypoints: Waypoint_upload[] = [];
  let map: L.Map;
  let polyline: L.Polyline;
  let captionsUrl = "/captions.vtt";
  let videoName = "";
  let cloud_videoUrl = "";
  let video: HTMLVideoElement;
  let noWaypointsMarker: any;
  let lastWaypoint: Waypoint_upload;
  let speed = 0;
  let country = "";
  let city = "";
  let comments: Comment[];
  let newComment = "";
  let username = "";
  let current_user_picture = "";
  let show_videos = true;
  let profilePicture = "";
  let selectedType = "videos";

  // search users
  let name = "";
  let order_by = "nr_videos";
  let is_ascending = false;
  let user_data: User[];

  // search videos
  let video_name = "";
  let order_by_video = "time";
  let is_ascending_video = false;
  let time_period = "";
  let videos: Video[];
  let upvotes: Upvote[];


  async function handleGoogleAuthentication(){
    const response = await fetch(
        `${SERVER_URL}/set_cookies/`,
          {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
            },
            credentials: "include",
            // redirect: "follow",

          },
        );
        
        const data = await response.json();
        // console.log(data)
        if (response.ok) {
        document.cookie = `csrftoken=${data.csrf_token}; path=/;`;
        document.cookie = `username=${data.username}; path=/;`;
        

        }

  }

  onMount(async () => {
    // handleGoogleAuthentication();

    username = get_cookie("username");
    const csrfToken = get_cookie("csrftoken");
    const response = await is_logged(username, csrfToken);

    // Read the custom header value
    let profilePictureGoogle= get_cookie("profile_picture"); 
  
    if (profilePictureGoogle) {
      // decode profile picture base64
      const decoded = decodeURIComponent(profilePictureGoogle);
      const replaced = decoded.replace(/-/g, '+').replace(/_/g, '/');
      const result = atob(replaced);
      profilePictureGoogle = decodeURIComponent(result);

      sessionStorage.setItem('profile_picture', profilePictureGoogle);
      // console.log(profilePictureGoogle);
      removeCookie('profile_picture');
    }


    const isBrowser = typeof window !== "undefined";

    if (isBrowser) {
      profilePicture = sessionStorage.getItem("profile_picture") || "";
      // console.log(profilePicture);
    }

    if (typeof window !== "undefined") {
      //gpx window

      //video window
      video = document.getElementById("video") as HTMLVideoElement;

      let intervalId: NodeJS.Timeout | null = null;
      let isPlaying = false;

      video.addEventListener("play", () => {
        isPlaying = true;
        const updateInterval = 200;

        const updateMapFunction = async () => {
          if (!isPlaying) return;

          const currentTime = video.currentTime;
          if (waypoints && waypoints.length > 0) {
            const currentArray= find_closest_waypoint(
              currentTime,
              waypoints,
            );
            const currentWaypoint=currentArray[0];
            lastWaypoint=waypoints[currentArray[1]];

            speed = await update_map(
              currentWaypoint,
              map,
              lastWaypoint,
              currentTime,
              speed,
              waypoints[0],
            );
  
            updateInfo(city, country, speed);
          }
        };

        intervalId = setInterval(updateMapFunction, updateInterval);
      });

      video.addEventListener("timeupdate", () => {
        isPlaying = true;
        const updateInterval = 200;

        const updateMapFunction = async () => {
          if (!isPlaying) return;

          const currentTime = video.currentTime;
          if (waypoints && waypoints.length > 0) {
            const currentArray= find_closest_waypoint(
              currentTime,
              waypoints,
            );
            const currentWaypoint=currentArray[0];
            lastWaypoint=waypoints[currentArray[1]];
            
            speed = await update_map(
              currentWaypoint,
              map,
              lastWaypoint,
              currentTime,
              speed,
              waypoints[0],
            );

            updateInfo(city, country, speed);
          }
        };

        intervalId = setInterval(updateMapFunction, updateInterval);
      });

      video.addEventListener("pause", () => {
        isPlaying = false;
        if (intervalId) {
          clearInterval(intervalId);
          intervalId = null;
        }
      });
    }
  });

  async function handleDownload(video_user: string) {
    const { username, csrfToken } = get_cookie_values();

    try {
      const { cloud_videoUrl, comments_received } = await downloadVideo(
        videoName,
        video_user,
      );

      // video
      if (cloud_videoUrl) {
        document.getElementById("video")?.setAttribute("src", cloud_videoUrl);

        waypoints = await loadGPXData(video_user, csrfToken, videoName);

        // new speed and waypoints
        if (waypoints) {
          lastWaypoint = waypoints[0];
          speed = 0;
        }

        // get city and country

        const LocationResponse = await fetch(
          `${SERVER_URL}/display_city_country/`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              username,
              csrf_token: csrfToken,
              video_name: videoName,
              video_user: video_user,
            }),
          },
        );

        if (LocationResponse.ok) {
          const data = await LocationResponse.json();
          city = data.city;
          country = data.country;
          updateInfo(city, country, 0);
        } else {
          city = "Unknown";
          country = "Unknown";
          updateInfo(city, country, 0);
        }
      }

      // comments
      if (comments_received) {
        comments = comments_received;
      }
    } catch (error) {
      console.error("Error:", error);
    }
  }

  async function loadGPXData(
    video_user: string,
    csrfToken: string,
    videoName: string,
  ) {
    const L = await import("leaflet");
    const username = get_cookie("username");

    // Initialize the map if it hasn't been initialized yet
    if (!map) {
      map = L.map("map").setView([51.505, -0.09], 13);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);
    }

    const gpxResponse = await fetch(`${SERVER_URL}/display_gpx/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        csrf_token: csrfToken,
        video_name: videoName,
        video_user: video_user,
      }),
    });

    const gpxData = await gpxResponse.json();
    const waypoints = gpxData.waypoints;

    // Remove the existing polyline if it exists
    if (polyline) {
      map.removeLayer(polyline);
    }

    if (gpxData.waypoints && gpxData.waypoints.length > 0) {
      if (noWaypointsMarker) {
        map.removeLayer(noWaypointsMarker);
        noWaypointsMarker = null;
      }

      // Add the new map route
      const latLngs = waypoints.map((point: { lat: number; lng: number }) => [
        point.lat,
        point.lng,
      ]);
      polyline = L.polyline(latLngs, { color: "blue" }).addTo(map);
      map.fitBounds(polyline.getBounds());
    } else {
      console.error("No waypoints found in GPX data.");

      const center = map.getCenter();
      const message = "No waypoints found";

      if (!noWaypointsMarker) {
        noWaypointsMarker = L.marker(center)
          .addTo(map)
          .bindPopup(message)
          .openPopup();
      }
    }

    return waypoints;
  }

  async function updateInfo(city: string, country: string, speed: number) {
    try {
      document.getElementById("speed")!.innerText = `Speed: ${speed} km/h`;
      document.getElementById("city")!.innerText = `City: ${city}`;
      document.getElementById("country")!.innerText = `Country: ${country}`;
    } catch (error) {
      console.error("Failed to update info:", error);
    }
  }

  async function handleUsersSubmit(event: Event) {
    event.preventDefault();
    const { username, csrfToken } = get_cookie_values();
    const response = await fetch(`${SERVER_URL}/display_search_users/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        csrf_token: csrfToken,
        name,
        order_by,
        is_ascending,
      }),
    });
    if (response.ok) {
      const data = await response.json();
      user_data = data;
      show_videos = false;
    } else {
      console.error("Failed to search users");
    }
  }

  async function handleVideosSubmit(event: Event) {
    event.preventDefault();
    const { username, csrfToken } = get_cookie_values();
    const response = await fetch(`${SERVER_URL}/display_search_videos/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        csrf_token: csrfToken,
        video_name,
        order_by: order_by_video,
        is_ascending: is_ascending_video,
        time_period,
      }),
    });
    if (response.ok) {
      const data = await response.json();
      videos = data.videos;
      upvotes = data.upvotes;
      show_videos = true;
      // console.log(videos)
      // console.log(upvotes)
    } else {
      console.error("Failed to search users");
    }
  }

  function no_keypress() {}

  function selectVideoName(name: string, video_user: string) {
    videoName = name;
    handleDownload(video_user);
  }

  async function handleUpVoteClick(video: Video, videoUser: string) {
    try {
      const videoName = video.video_name;
      const success = await handleUpVote(videoName, videoUser);
      if (success) {
        const videoIndex = videos.findIndex((v) => v.video_name === videoName);
        const existingUpvoteIndex = upvotes.findIndex(
          (upvote: Upvote) => upvote.video_name === videoName,
        );
        if (existingUpvoteIndex !== -1) {
          // exista deja
          videos[videoIndex] = {
            ...videos[videoIndex],
            nr_likes: videos[videoIndex].nr_likes - 1,
          };
          upvotes = [
            ...upvotes.slice(0, existingUpvoteIndex),
            ...upvotes.slice(existingUpvoteIndex + 1),
          ];
        } else {
          // nu exista
          videos[videoIndex] = {
            ...videos[videoIndex],
            nr_likes: videos[videoIndex].nr_likes + 1,
          };
          upvotes = [...upvotes, { video_name: videoName }];
        }
      } else {
        console.error("Failed to upvote.");
      }
    } catch (error) {
      console.error("Error upvoting:", error);
    }
  }

  function isUpvoted(videoName: string) {
    return upvotes.some((upvote: Upvote) => upvote.video_name === videoName);
  }

  async function handleCommentButtonClick() {
    try {
      const success = await handleCommentButton(newComment, videoName);
      if (success[0]) {
        if (current_user_picture === "") {
          const profilePictureData = await fetchProfilePicture("not_start");
          current_user_picture = profilePictureData.profile_picture;
        }

        comments = [
          {
            // timestamp: new Date().toISOString(),
            timestamp : success[1],
            comment: newComment,
            username: username,
            profile_picture: current_user_picture,
          },
          ...comments,
        ];
      } else {
        alert("Failed to submit comment.");
      }

      // Reset the input field after the comment is submitted
      newComment = "";
    } catch (error) {
      console.error("Failed to submit comment:", error);
    }
  }

  async function handleDeleteComment(comment: Comment) {
    const success = await deleteComment(comment);
    if (success) {
      comments = comments.filter((c) => c !== comment);
    } else {
      alert("Failed to delete comment.");
    }
  }
</script>

<svelte:head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tenkai</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <link
    rel="stylesheet"
    href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
  />
</svelte:head>

<!-- Navbar -->

<div
  class="h-screen w-48 bg-gray-800 fixed top-0 left-0 flex flex-col items-center py-4 shadow-lg"
>

  <div class="flex flex-col items-center mt-4">


    <div class="mb-8">
      {#if profilePicture}
        <img
          src={profilePicture}
          alt=""
          class="w-16 h-16 rounded-full border-2 border-white"
        />
      {:else}
        <div class="w-16 h-16 rounded-full border-2 border-white flex"></div>
      {/if}
    </div>
    <button
      class="mb-4 w-full text-white py-2 px-4 rounded hover:bg-gray-700 flex items-center"
      on:click={logout_user}
    >
      <i class="fas fa-sign-out-alt mr-2"></i>Logout
    </button>
    <button
      class="mb-4 w-full text-white py-2 px-4 rounded hover:bg-gray-700 flex items-center"
      on:click={redirectToHome}
    >
      <i class="fas fa-home mr-2"></i>Home
    </button>
    <button
      class="mb-4 w-full text-white py-2 px-4 rounded hover:bg-gray-700 flex items-center"
      on:click={redirectToProfile}
    >
      <i class="fas fa-user mr-2"></i>Profile
    </button>
    <button
      class="mb-4 w-full text-white py-2 px-4 rounded hover:bg-gray-700 flex items-center"
      on:click={redirectToUpload}
    >
      <i class="fas fa-upload mr-2"></i>Upload
    </button>
    <button
      class="mb-4 w-full text-white py-2 px-4 rounded hover:bg-gray-700 flex items-center"
      on:click={redirectToLogin}
    >
      <i class="fas fa-sign-in-alt mr-2"></i>Login
    </button>
    <button
      class="mb-4 w-full text-white py-2 px-4 rounded hover:bg-gray-700 flex items-center"
      on:click={redirectToSignUp}
    >
      <i class="fas fa-user-plus mr-2"></i>Sign up
    </button>
    
  </div>
  <img
src="logo.png"
alt="Logo"
 class="w-36 h-36 object-contain mt-auto mb-4"
/>
</div>

<!-- Page Loadout -->
<div class="ml-52 mt-8 flex flex-col">
  <div class="flex justify-center items-center space-x-4">
    <!-- Select Button -->
    <select
      class="border border-gray-300 rounded p-2"
      bind:value={selectedType}
    >
      <option value="users">Search Users</option>
      <option value="videos">Search Videos</option>
    </select>

    <!-- Search Forms -->
    <div class="flex justify-center space-x-4">
      <!-- Search Users Form -->
      {#if selectedType === "users"}
        <form on:submit={handleUsersSubmit} class="flex flex-col space-y-4">
          <div class="flex items-center space-x-4">
            <label for="name" class="text-sm"></label>
            <input
              type="text"
              id="name"
              bind:value={name}
              placeholder="Name"
              class="border border-gray-300 rounded p-2"
            />

            <label for="order_by" class="text-sm"></label>
            <select
              id="order_by"
              bind:value={order_by}
              class="border border-gray-300 rounded p-2"
            >
              <option value="nr_videos">Number of Videos</option>
              <option value="nr_upvotes">Number of Upvotes</option>
            </select>

            <div class="flex flex-col">
              <label class="text-sm">
                <input
                  type="radio"
                  bind:group={is_ascending}
                  value={true}
                  class="mr-1"
                /> Ascending
              </label>
              <label class="text-sm">
                <input
                  type="radio"
                  bind:group={is_ascending}
                  value={false}
                  class="mr-1"
                /> Descending
              </label>
            </div>

            <button
              type="submit"
              class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
              >Search</button
            >
          </div>
        </form>
      {/if}

      <!-- Search Videos Form -->
      {#if selectedType === "videos"}
        <form
          on:submit|preventDefault={handleVideosSubmit}
          class="flex flex-col space-y-4"
        >
          <div class="flex items-center space-x-4">
            <label for="video_name" class="text-sm"></label>
            <input
              id="video_name"
              type="text"
              bind:value={video_name}
              placeholder="Video Name"
              class="border border-gray-300 rounded p-2"
            />

            <label for="order_by_video" class="text-sm"></label>
            <select
              id="order_by_video"
              bind:value={order_by_video}
              class="border border-gray-300 rounded p-2"
            >
              <option value="time">Time</option>
              <option value="nr_upvotes">Number of Upvotes</option>
            </select>

            <div class="flex flex-col">
              <label class="text-sm">
                <input
                  type="radio"
                  bind:group={is_ascending_video}
                  value={true}
                  class="mr-1"
                /> Ascending
              </label>
              <label class="text-sm">
                <input
                  type="radio"
                  bind:group={is_ascending_video}
                  value={false}
                  class="mr-1"
                /> Descending
              </label>
            </div>

            <label for="time_period" class="text-sm"></label>
            <select
              id="time_period"
              bind:value={time_period}
              class="border border-gray-300 rounded p-2"
            >
              <option value="">All time</option>
              <option value="today">Today</option>
              <option value="last_week">Last Week</option>
              <option value="last_month">Last Month</option>
              <option value="last_year">Last Year</option>
            </select>

            <button
              type="submit"
              class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
              >Search</button
            >
          </div>
        </form>
      {/if}
    </div>
  </div>

  <div class="flex flex-wrap justify-between mt-8 space-x-8">

   <!-- Users Section -->
{#if user_data && !show_videos}
  <div class="w-full md:w-2/3 lg:w-1/2">
    <div class="border-4 border-double border-indigo-800 flex justify-center max-h-9">
      <h2 class="text-lg font-bold mb-4 text-center">Users</h2>
    </div>

    <div class="mb-8 border-l-4 border-r-4 border-b-4 border-double border-indigo-800">
      {#if user_data.length > 0}
        <div class="overflow-y-auto max-h-96 container_videos">
          <ul class="space-y-4">
            {#each user_data as user}
              <li class="border p-4 rounded-lg">
                <div
                  class="flex items-center mb-2"
                  role="button"
                  tabindex="0"
                  on:click={() => redirectToUserProfile(user.name)}
                  on:keypress={no_keypress}
                  style="max-width: fit-content;"
                >
                  <img
                    src={user.image_link}
                    alt={user.name}
                    class="w-12 h-12 rounded-full"
                  />
                  <p class="font-bold ml-4">{user.name}</p>
                </div>
                <p class="text-lg font-bold">
                  Videos: {user.nr_videos} Upvotes: {user.nr_upvotes}
                </p>
              </li>
            {/each}
          </ul>
        </div>
      {:else}
        <p class="text-gray-500">No users available.</p>
      {/if}
    </div>
  </div>
{/if}


    <!-- Videos Section -->
    {#if show_videos}
    <div class="w-full md:w-2/3 lg:w-1/2">
      <div
        class=" border-4 border-double border-indigo-800 flex justify-center max-h-9"
      >
        <h2 class="text-lg font-bold mb-4 text-center">Videos</h2>
      </div>

      <div
        class="mb-8 border-l-4 border-r-4 border-b-4 border-double border-indigo-800"
      >
        {#if videos && upvotes}
          {#if (videos?.length || 0) > 0}
            <div class="overflow-y-auto max-h-96 container_videos">
              <ul class="space-y-4">
                {#each videos as video}
                  <li class="border p-4 rounded-lg">
                    <div
                      class="flex items-center mb-2"
                      role="button"
                      tabindex="0"
                      on:click={() => redirectToUserProfile(video.username)}
                      on:keypress={no_keypress}
                      style="max-width: fit-content;"
                    >
                      <img
                        src={video.image_link}
                        alt={video.username}
                        class="w-12 h-12 rounded-full"
                      />
                      <p class="font-bold ml-4">{video.username}</p>
                    </div>
                    <p class="text-lg font-bold">
                      Name: {video.video_name.replace(".mp4", "")}
                    </p>
                    <p class="text-sm text-gray-600">{timeAgo(video.timestamp)}</p>
                    <p class="container_text">
                      Description: {video.description}
                    </p>
                    <p class="container_text">
                      Location: {video.country
                        ? video.country + ", "
                        : ""}{video.city ? video.city : "Unknown"}
                    </p>

                    <div class="flex justify-between items-center mt-2">
                      <div>
                        <button
                          on:click={() =>
                            selectVideoName(video.video_name, video.username)}
                          class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2.5 px-4 rounded"
                        >
                          Select
                        </button>
                        <button
                          on:click={() =>
                            handleUpVoteClick(video, video.username)}
                          class:selected={upvotes.some(
                            (upvote) => upvote.video_name === video.video_name,
                          )}
                          class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded"
                        >
                          {#if isUpvoted(video.video_name)}
                            <div class="flex items-center">
                              <i class="fas fa-thumbs-up text-white"></i>
                              <p class="ml-2 text-sm">{video.nr_likes}</p>
                            </div>
                          {:else}
                            <div class="flex items-center">
                              <i class="far fa-thumbs-up text-white"></i>
                              <p class="ml-2 text-sm">{video.nr_likes}</p>
                            </div>
                          {/if}
                        </button>
                      </div>
                    </div>
                  </li>
                {/each}
              </ul>
            </div>
          {:else}
            <p class="text-gray-500">No videos available.</p>
          {/if}
        {:else}
          <p class="text-gray-500">Search for a video or user.</p>
        {/if}
      </div>
    </div>
    {/if}

    <!-- Comments Section -->
    <div class="w-full md:w-1/3 lg:w-1/3 pr-4">
      <div
        class="border-4 border-double border-indigo-800 flex justify-center max-h-9"
      >
        <h2 class="text-lg font-bold mb-4 text-center">Comments</h2>
      </div>

      <div
        class=" mb-8 border-l-4 border-r-4 border-b-4 border-double border-indigo-800 max-h-96 overflow-y-auto container_comments"
      >
        {#if comments}
          <div
            class="overflow-y-auto max-h-96 container_comments p-4 container_comments"
          >
            <input
              type="text"
              bind:value={newComment}
              placeholder="Add your comment here"
              class="w-full mb-4 p-2 border border-gray-300 rounded"
              maxlength="200"
            />
            <button
              on:click={handleCommentButtonClick}
              class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mb-4 w-full"
              disabled={newComment.trim().length === 0}
            >
              Submit Comment
            </button>
            {#if comments.length > 0}
              {#each comments as comment}
                <div class="comment mb-4 p-4 border rounded-lg">
                  <div
                    class="flex items-center mb-2"
                    style="max-width: fit-content;"
                    on:click={() => redirectToUserProfile(comment.username)}
                    role="button"
                    tabindex="0"
                    on:keypress={no_keypress}
                  >
                    <img
                      src={comment.profile_picture}
                      alt=""
                      class="w-12 h-12 rounded-full"
                    />
                    <div class="ml-4">
                      <p class="font-bold">{comment.username}</p>
                      <p class="text-sm text-gray-600">
                        {timeAgo(comment.timestamp)}
                      </p>
                    </div>
                  </div>
                  <p class="mb-2 container_text">{comment.comment}</p>
                  {#if username === comment.username}
                    <button
                      on:click={() => handleDeleteComment(comment)}
                      class="text-red-500 hover:underline"
                    >
                      Delete
                    </button>
                  {/if}
                </div>
              {/each}
            {:else}
              <p class="text-gray-500">No comments available.</p>
            {/if}
          </div>
        {:else}
          <div class="overflow-y-auto max-h-96 container_comments p-4">
            <p class="text-gray-500">Select a video for comments to appear.</p>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<!-- Map and Video Section-->
<div class="ml-48 mt-8 flex flex-col">
  <div class="bg-gray-200 rounded-lg p-4 max-w-screen-lg mx-auto">
    <div id="info" class="flex justify-center gap-8">
      <p id="speed">Speed:</p>
      <p id="city">City:</p>
      <p id="country">Country:</p>
    </div>
  </div>

  <div class="flex justify-center">
    {#if videoName ===""}
  <div class="relative w-1/2" style="height: 500px;">
    <div class="absolute inset-0 border border-black map-placeholder" ></div>
    <div class="absolute inset-0 bg-teal-100 bg-opacity-50"></div>
</div>
  {:else}
  <div id="map" class="w-1/2 border border-black" style="height: 500px;"></div>
{/if}

    <video id="video" controls class="w-1/2 h-500 bg-neutral-800">
      <track kind="captions" src={captionsUrl} srclang="en" label="English" />
      {#if cloud_videoUrl}
        <source src={cloud_videoUrl} type="video/mp4" />
        Your browser does not support the video tag.
      {/if}
    </video>
  </div>
</div>
