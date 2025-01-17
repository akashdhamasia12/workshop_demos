import torch
import intel_extension_for_pytorch as ipex
# torch_device = "cuda" if torch.cuda.is_available() else "cpu"
torch_device = "xpu"

from transformers import CLIPTextModel, CLIPTokenizer
from diffusers import AutoencoderKL, UNet2DConditionModel, PNDMScheduler

# 1. Load the autoencoder model which will be used to decode the latents into image space. 
vae = AutoencoderKL.from_pretrained("CompVis/stable-diffusion-v1-4", subfolder="vae")

# 2. Load the tokenizer and text encoder to tokenize and encode the text. 
tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
text_encoder = CLIPTextModel.from_pretrained("openai/clip-vit-large-patch14")

# 3. The UNet model for generating the latents.
unet = UNet2DConditionModel.from_pretrained("CompVis/stable-diffusion-v1-4", subfolder="unet")

from diffusers import LMSDiscreteScheduler

scheduler = LMSDiscreteScheduler.from_pretrained("CompVis/stable-diffusion-v1-4", subfolder="scheduler")

vae = vae.to(torch_device)
text_encoder = text_encoder.to(torch_device)
unet = unet.to(torch_device) 

vae = ipex.optimize(vae)
text_encoder = ipex.optimize(text_encoder)
unet = ipex.optimize(unet)

#vae = ipex.optimize(vae, dtype=torch.bfloat16)
#text_encoder = ipex.optimize(text_encoder, dtype=torch.bfloat16)
#unet = ipex.optimize(unet, dtype=torch.bfloat16)

prompt = ["a photograph of an astronaut riding a horse"]

height = 512                        # default height of Stable Diffusion
width = 512                         # default width of Stable Diffusion

num_inference_steps = 20            # Number of denoising steps

guidance_scale = 7.5                # Scale for classifier-free guidance

generator = torch.manual_seed(32)   # Seed generator to create the inital latent noise

batch_size = 1


text_input = tokenizer(prompt, padding="max_length", max_length=tokenizer.model_max_length, truncation=True, return_tensors="pt")

with torch.no_grad():
  text_embeddings = text_encoder(text_input.input_ids.to(torch_device))[0]

max_length = text_input.input_ids.shape[-1]
uncond_input = tokenizer(
    [""] * batch_size, padding="max_length", max_length=max_length, return_tensors="pt"
)
with torch.no_grad():
  uncond_embeddings = text_encoder(uncond_input.input_ids.to(torch_device))[0] 

text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

latents = torch.randn(
  (batch_size, unet.in_channels, height // 8, width // 8),
  generator=generator,
)
latents = latents.to(torch_device)

scheduler.set_timesteps(num_inference_steps)

latents = latents * scheduler.init_noise_sigma

from tqdm.auto import tqdm
from torch import autocast

#Warmup steps

print("warmup steps")    
for t in tqdm(scheduler.timesteps):
  # expand the latents if we are doing classifier-free guidance to avoid doing two forward passes.
  latent_model_input = torch.cat([latents] * 2)

  latent_model_input = scheduler.scale_model_input(latent_model_input, t)

  # predict the noise residual
  with torch.no_grad():
    noise_pred = unet(latent_model_input, t, encoder_hidden_states=text_embeddings).sample

  # perform guidance
  #noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
  #noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

  # compute the previous noisy sample x_t -> x_t-1
  #latents = scheduler.step(noise_pred, t, latents).prev_sample

print("Actual steps")

for t_ in tqdm(scheduler.timesteps):
  # expand the latents if we are doing classifier-free guidance to avoid doing two forward passes.
  latent_model_input = torch.cat([latents] * 2)

  latent_model_input = scheduler.scale_model_input(latent_model_input, t_)

  # predict the noise residual
  with torch.no_grad():
    noise_pred = unet(latent_model_input, t_, encoder_hidden_states=text_embeddings).sample

  # perform guidance
  noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
  noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

  # compute the previous noisy sample x_t -> x_t-1
  latents = scheduler.step(noise_pred, t_, latents).prev_sample


  # scale and decode the image latents with vae
latents = 1 / 0.18215 * latents

with torch.no_grad():
  image = vae.decode(latents).sample

image = image.detach().cpu()

# image.save("image_test.png")
import numpy as np

from PIL import Image
# image = (image / 2 + 0.5).clamp(0, 1)
image = (image / 2 + 0.5).clip(0, 1)
# print(image.shape)
image = np.transpose(image, (0, 2, 3, 1))
print(image.shape)
# image = image.detach().cpu().permute(0, 2, 3, 1).numpy()
image = image.numpy()

images = (image * 255).round().astype("uint8")

pil_images = [Image.fromarray(image) for image in images]
# pil_images[0]

pil_images[0].save("image_sd.png")

